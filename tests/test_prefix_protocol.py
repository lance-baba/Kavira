"""T04(a) —— 检索前缀协议单元测试（**空前缀 = 零变化**，不依赖具体 artifact）。

验证（团队拍板 ①）：
  1. `BaseEmbedder.embed_query/embed_documents` 在**空前缀**下与直接 `embed` **完全一致**
     （空前缀资源 ⇒ 行为零变化；随包 artifact 可声明前缀，如 e5 的 query:/passage:，
      但本项契约是「空 ⇒ 与 embed 等价」，与具体 artifact 无关）；
  2. 非空前缀下按用途施加（query→query_prefix；document→document_prefix）；
  3. `EmbeddingResource` 的 `query_prefix/document_prefix` 默认 `""`，且能从 artifact.json 解析；
  4. `signature_extra()`：空前缀**不计入**；非空时纳入（换前缀=需重建）。

纯合成、无需模型/onnxruntime，任何环境都跑。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PASS: list[str] = []
FAIL: list[str] = []
SKIP: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    (PASS if cond else FAIL).append(name if cond else f"{name} :: {detail}")
    print(("  ✅ " if cond else "  ❌ ") + name + ("" if cond else f"  [{detail}]"))
    return cond


def section(t: str) -> None:
    print(f"\n── T04(a) {t} " + "─" * max(0, 48 - len(t)))


def _fake_embedder(query_prefix="", document_prefix=""):
    from app.core import embedder as E

    class _Fake(E.BaseEmbedder):
        def __init__(self):
            super().__init__(3)
            self.query_prefix = query_prefix
            self.document_prefix = document_prefix

        def embed(self, texts):  # 向量 = 文本长度（可判定前缀是否被施加）
            return [[float(len(t))] for t in texts]

    return _Fake()


def run_prefix_tests() -> None:
    from tests import test_env as _te

    _te.assert_test_library_safe()
    print("\n" + "=" * 66)
    print("  T04(a) —— 检索前缀协议单测")
    print("=" * 66)

    # 1) 空前缀 = 与 embed 完全一致
    section("空前缀 = 零变化（与 embed 等价）")
    g = _fake_embedder()
    check("embed_query == embed([q])[0]", g.embed_query("hello") == g.embed(["hello"])[0])
    check("embed_documents == embed(texts)",
          g.embed_documents(["hi", "yo"]) == g.embed(["hi", "yo"]))
    check("BaseEmbedder 默认前缀为空",
          g.query_prefix == "" and g.document_prefix == "")

    # 2) 非空前缀按用途施加
    section("非空前缀按用途施加")
    f = _fake_embedder(query_prefix="query: ", document_prefix="passage: ")
    check("query 加 query_prefix", f.embed_query("hello") == [float(len("query: hello"))])
    check("document 加 document_prefix",
          f.embed_documents(["hi", "yo"]) == [[float(len("passage: hi"))],
                                              [float(len("passage: yo"))]])
    check("query/document 前缀互不串味",
          f.embed_query("x")[0] == float(len("query: x"))
          and f.embed_documents(["x"])[0][0] == float(len("passage: x")))

    # 3) EmbeddingResource 默认 + 解析
    section("EmbeddingResource 前缀解析")
    from app.core import embedder as E
    import dataclasses
    res, code, why = E.load_embedding_resource(Path(REPO / "vendor" / "cache" / "embedding"))
    if res is None:
        SKIP.append(f"资源未取件（{code}）")
        print(f"  ⏭ 跳过资源解析用例（{code}: {why}）")
    else:
        # 随包 artifact 可声明前缀（如 e5 系 query:/passage:）；不假定具体值，只断言解析自洽 + 签名规则。
        check("随包资源前缀解析为字符串",
              isinstance(res.query_prefix, str) and isinstance(res.document_prefix, str))
        empty = dataclasses.replace(res, query_prefix="", document_prefix="")
        check("空前缀资源签名不含前缀键",
              set(empty.signature_extra()) == {"artifact_sha256", "tokenizer_sha256", "precision"})
        check("非空前缀纳入签名",
              set(dataclasses.replace(res, query_prefix="q: ",
                                      document_prefix="p: ").signature_extra())
              >= {"query_prefix", "document_prefix"})

        # 4) 从一个「无前缀键」的临时 manifest 解析 → 默认空
        tmp = Path(tempfile.mkdtemp(prefix="kavira-prefix-manifest-"))
        try:
            (tmp / "model.onnx").write_bytes(b"x")            # 只需存在 + 尺寸匹配
            (tmp / "tokenizer.json").write_bytes(b"y")
            (tmp / "artifact.json").write_text(json.dumps({
                "format_version": 1, "id": "t", "artifact_source": "s",
                "artifact_revision": "r", "artifact_sha256": "0" * 64,
                "artifact_size": 1, "precision": "int8", "dimension": 3,
                "local_files": {"model": "model.onnx", "tokenizer": "tokenizer.json"},
            }, ensure_ascii=False), encoding="utf-8")
            r2, code2, why2 = E.load_embedding_resource(tmp)
            check("缺前缀键 → 默认空（不报错）",
                  r2 is not None and r2.query_prefix == "" and r2.document_prefix == "",
                  f"{code2}: {why2}")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n  T04(a) TOTAL={len(PASS) + len(FAIL) + len(SKIP)} "
          f"PASS={len(PASS)} SKIP={len(SKIP)} FAIL={len(FAIL)}")


if __name__ == "__main__":
    run_prefix_tests()
    raise SystemExit(1 if FAIL else 0)
