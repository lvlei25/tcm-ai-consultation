# spec-008：测试与规范补齐

对应基线：spec-001「测试」章节、spec-004「验证」章节

## 变更原因

现 32 例单测集中在 config / loader / retriever / pipeline 四个模块的纯函数，存在四处覆盖缺口：

1. `kb/builder.py` 构建链路无用例（产物一致性、空语料异常）
2. spec-004 的 AppTest 断言（8 个分组标题）为手工执行，未沉淀为 pytest 用例
3. 诊断输出只测到「消息构造」，未校验真实输出的六小节结构
4. 缺少防 Key 泄露的自动检查：真实 Key 一旦误入被跟踪文件，无任何用例拦截

## 设计依据

- spec-001 要求测试覆盖「知识库检索、问诊单整理、诊断结果输出」三类
- 真实 LLM 调用不进默认测试集，用 `pytest.mark.integration` 隔离，Key 仍只从 `.env` 读取
- 泄露检查只扫「被 git 跟踪的文件」，不扫 `.env` 本身，避免误报与泄露

## 变更内容

| 文件 | 变更 |
|------|------|
| tests/test_builder.py | 新增：分块产物与 chunks.json 一致、BM25 索引可加载、空语料抛异常、向量化批次切分边界（配合 spec-006） |
| tests/test_app.py | 新增：AppTest 断言 8 个分组标题渲染（基本信息/望诊与切诊/问寒热与汗出/问头身胸腹/问饮食口味/问睡眠情志/问二便与经期/其他伴随症状），无运行异常 |
| tests/test_integration.py | 新增：标记 `integration`，默认跳过；`-m integration` 时真实调用 `generate_query` 与 `stream_diagnosis`，断言检索语句非空且 ≤80 字、诊断输出含六小节标题；Key 仅经 `config.get_api_key()` 读取 |
| tests/test_security.py | 新增：用 `git ls-files` 取被跟踪文件列表，扫描其中不含 `sk-` 开头的真实 Key 串；命中即失败并提示轮换 Key |
| conftest.py | 新增 `integration` marker 注册，避免 PytestUnknownMarkWarning |
| pytest 配置 | 在 conftest 或 pytest.ini 中默认 `addopts = -m "not integration"` |

## 验证

- `python -m pytest tests/ -q` 全量通过（用例总数由 32 增至 40+）
- `python -m pytest tests/ -q -m integration` 在有 Key 与知识库时通过
- `tests/测试文档.md` 同步更新用例清单与运行方式

## 注意事项

- 集成用例不得硬编码 Key，不得写入真实 Key 到任何测试文件
- 集成用例缺省跳过，保证离线环境 `pytest` 仍全绿、不产生费用
- 泄露扫描用例如命中，需在轮换 Key 后方可恢复通过

## 修订

- 2026-10-17：`kb/builder.py` 的缓存函数改为调用时解析 `EMB_CACHE_FILE`（`path=None`），
  否则默认参数在导入期绑定，测试无法重定向缓存路径，导致用例间相互污染
- 2026-10-17：`tests/test_app.py` 用项目根目录绝对路径构造 `AppTest.from_file`，
  相对路径会被解析到 tests 目录下

## 验证结果（2026-10-17 执行）

- `python -m pytest tests/ -q` → 41 passed, 3 deselected（约 5 秒，离线、无费用）
- `python -m pytest tests/ -m integration -q` → 3 passed（191 秒，真实调用通过）
- 新增用例：builder 6 例、app 2 例、security 1 例、integration 3 例
- `tests/测试文档.md` 同步更新：覆盖范围表 + 用例清单扩至 44 例（41 离线 + 3 集成）
- 向量缓存已用既有索引回填 3195 条，下次构建无需重复向量化
