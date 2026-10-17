# spec-006：知识库构建流程健壮性

对应基线：spec-001-中医AI问诊平台搭建.md

## 变更原因

`kb/builder.py` 当前为一次性全量构建：3.1 MB 语料单次 `FAISS.from_documents` 向量化，
无分批、无进度、无断点；构建开头即 `shutil.rmtree(KB_DIR)` 清空旧产物。
一旦中途失败（网络抖动、额度不足、接口限流），旧产物已删、新产物未成，
必须从头重跑全部向量化，重复付出费用与时间。

## 设计依据

- 大语料分批：降低单次请求失败的影响面，失败仅重做当前批次
- 先写临时目录、成功后原子替换：避免构建失败破坏既有可用产物
- 断点续建：以文本块内容的哈希为键缓存向量，重跑时跳过已向量化块
- 全程中文进度输出，符合 spec-001「无 fallback、中文注释」约束

## 变更内容

| 文件 | 变更 |
|------|------|
| config.py | 新增 `EMBED_BATCH_SIZE`（默认 25）常量 |
| kb/builder.py | 新增 `iter_batches()`：按 `EMBED_BATCH_SIZE` 切分文档列表 |
| kb/builder.py | 新增 `embed_documents()`：分批调用 `FAISS.from_documents` 增量合并（`merge_from`），每批打印中文进度（已完成/总数） |
| kb/builder.py | 新增 `save_artifacts()`：产物先写入 `storage/kb_tmp/`，全部成功后替换 `storage/kb/` |
| kb/builder.py | 新增向量缓存 `storage/emb_cache.json`（块文本 sha1 → 向量），`build_knowledge_base(use_cache=True)` 命中则跳过 |
| kb/builder.py | 返回统计扩展为 `{"块数": n, "向量化块数": m, "耗时秒": t}` |
| scripts/build_kb.py | 打印块数、向量化块数（缓存命中情况）、耗时；支持 `--no-cache` 参数强制全量重建 |

## 验证

- `python -m pytest tests/ -q` 全量通过（含新增 `tests/test_builder.py`，见 spec-008）
- 正常构建：产物齐全，统计含块数与耗时
- 二次构建：缓存命中，向量化块数为 0，耗时显著下降
- 构建中断（人为中断后重跑）：旧产物仍可用，重跑可续建

## 注意事项

- 不引入 fallback：失败即抛出明确中文异常，不静默降级
- 缓存文件与临时目录加入 `.gitignore`（`storage/` 已被忽略，无需新增规则）
- 分批大小与是否默认启用缓存以实测耗时为准，结论回写本 spec「验证结果」

## 修订

- 2026-10-17：向量缓存改用 `storage/emb_cache.pkl`（pickle）而非 spec 初稿的 JSON，
  避免 3195 块 × 1024 维向量产生数十 MB 文本；建索引改用 `FAISS.from_embeddings`
  一次性载入已算向量，比 `merge_from` 逐批合并更直接

## 验证结果（2026-10-17 执行）

- 小型语料（24 块）两次构建：首次 `{'块数': 24, '向量化块数': 24, '耗时秒': 4.3}`，
  二次 `{'块数': 24, '向量化块数': 0, '耗时秒': 0.0}`，缓存命中生效，进度按批打印
- 产物经 `storage/kb_tmp/` 写入后替换 `storage/kb/`，临时目录构建后自动清理
- 既有知识库（3195 块）不受影响：`load_knowledge_base()` 正常，检索仍返回 6 条，最高融合分 0.601
- `python -m pytest tests/ -q` → 32 passed
- 脚本输出改为：块数 + 新向量化块数 + 耗时，支持 `python scripts/build_kb.py --no-cache`
