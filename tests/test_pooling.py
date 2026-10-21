"""P0-0 —— pooling 修复单元测试（`OnnxEmbedder._pool`）。

验证（PRD §5 / 目标 G4）：
  1. ``cls``  → ``last_hidden[:, 0, :]``（与历史硬编码逐位一致）；
  2. ``mean`` → 按 ``attention_mask`` 加权平均并**排除 padding**：
     ``(h * m).sum(1) / clip(m.sum(1), 1e-9)``；
  3. 未知 / 漏声明 pooling → ``probe()`` 判不可用（**不默认 CLS 蒙混**）。

分段：
  * A/B/C/D/E 用**合成数组**，不需要模型/onnxruntime —— 任何环境都跑；
  * F 用**真实模型**验证 mean 与 cls 不同、mean 与 numpy 手算 < 1e-6（缺资源时 SKIP）。

风格与 ``tests/test_embedding_a42b.py`` 一致（check/skip/section）。
"""
from __future__ import annotations

import dataclasses
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RESOURCE_DIR = REPO / "vendor" / "cache" / "embedding"

PASS: list[str] = []
FAIL: list[str] = []
SKIP: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    (PASS if cond else FAIL).append(name if cond else f"{name} :: {detail}")
    print(("  ✅ " if cond else "  ❌ ") + name + ("" if cond else f"  [{detail}]"))
    return cond


def skip(name: str, reason: str = "") -> None:
    SKIP.append(f"{name} :: {reason}" if reason else name)
    print("  ⏭ " + name + (f"  [{reason}]" if reason else ""))


def section(t: str) -> None:
    print(f"\n── P0-0 {t} " + "─" * max(0, 52 - len(t)))


def _have_runtime_deps() -> tuple[bool, str]:
    try:
        import onnxruntime  # noqa: F401
        import tokenizers   # noqa: F401
        import numpy        # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return False, f"缺运行时依赖（{type(exc).__name__}）"
    return True, ""


def _have_resource() -> tuple[bool, str]:
    if not (RESOURCE_DIR / "artifact.json").is_file():
        return False, "未取件：先跑 scripts/fetch_embedding_resource.py"
    return True, ""


def _pool_with(pooling: str, last_hidden, mask):
    """不加载模型，只用合成数组直接调 ``OnnxEmbedder._pool``。"""
    import numpy as np

    from app.core import embedder as emb_mod

    stub = types.SimpleNamespace(
        _np=np, resource=types.SimpleNamespace(pooling=pooling))
    return emb_mod.OnnxEmbedder._pool(stub, last_hidden, mask)


# ---------------------------------------------------------------------------
# A —— cls == last_hidden[:, 0, :]
# ---------------------------------------------------------------------------
def _t_a_cls() -> None:
    section("A cls = last_hidden[:, 0, :]")
    import numpy as np

    last_hidden = np.arange(2 * 5 * 4, dtype=np.float32).reshape(2, 5, 4)
    mask = np.ones((2, 5), dtype=np.int64)
    got = _pool_with("cls", last_hidden, mask)
    check("A1 cls 取 token 0", np.array_equal(got, last_hidden[:, 0, :]))
    check("A2 cls 与 padding 无关（改 padding 位不变）",
          np.array_equal(
              _pool_with("cls", last_hidden, np.array([[1, 1, 0, 0, 0],
                                                       [1, 1, 1, 0, 0]], dtype=np.int64)),
              last_hidden[:, 0, :]))


# ---------------------------------------------------------------------------
# B —— mean 排除 padding，与 numpy 手算一致
# ---------------------------------------------------------------------------
def _t_b_mean() -> None:
    section("B mean = 按 mask 加权平均且排除 padding")
    import numpy as np

    last_hidden = np.array(
        [[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [0, 0, 0, 0], [0, 0, 0, 0]],
         [[2, 4, 6, 8], [1, 1, 1, 1], [3, 3, 3, 3], [9, 9, 9, 9], [9, 9, 9, 9]]],
        dtype=np.float32)
    # 行0: 3 个真 token；行1: 2 个真 token（后 3 个是 padding，且值非零 —— 必须被排除）
    mask = np.array([[1, 1, 1, 0, 0], [1, 1, 0, 0, 0]], dtype=np.int64)

    got = _pool_with("mean", last_hidden, mask)

    m = mask.astype(np.float32)[:, :, None]
    hand = (last_hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
    check("B1 mean 与 numpy 手算逐元素 < 1e-6",
          float(np.max(np.abs(got - hand))) < 1e-6,
          f"max={float(np.max(np.abs(got - hand))):.2e}")

    # 手工期望值（行0 = (1..12 的 3 组)/3；行1 = (2..8 + 1..1)/2）
    exp0 = np.array([5.0, 6.0, 7.0, 8.0], dtype=np.float32)      # (1+5+9)/3 ...
    exp1 = np.array([1.5, 2.5, 3.5, 4.5], dtype=np.float32)      # (2+1)/2 ...
    check("B2 行0 期望值正确", np.allclose(got[0], exp0, atol=1e-6), str(got[0]))
    check("B3 行1 期望值正确", np.allclose(got[1], exp1, atol=1e-6), str(got[1]))
    check("B4 padding 位（值=9）未被计入",
          not np.allclose(got[1], (np.array([2, 4, 6, 8]) + np.array([1, 1, 1, 1])
                                   + 3 * np.array([9, 9, 9, 9])) / 5.0, atol=1e-6))


# ---------------------------------------------------------------------------
# C —— mean != cls（同一输入）
# ---------------------------------------------------------------------------
def _t_c_mean_differs() -> None:
    section("C mean != cls")
    import numpy as np

    last_hidden = np.random.RandomState(0).randn(3, 6, 8).astype(np.float32)
    mask = np.array([[1, 1, 1, 1, 0, 0], [1, 1, 0, 0, 0, 0],
                     [1, 1, 1, 1, 1, 1]], dtype=np.int64)
    v_cls = _pool_with("cls", last_hidden, mask)
    v_mean = _pool_with("mean", last_hidden, mask)
    check("C1 两种池化结果不同", float(np.max(np.abs(v_cls - v_mean))) > 0.0)


# ---------------------------------------------------------------------------
# D —— 未知 pooling → raise
# ---------------------------------------------------------------------------
def _t_d_unknown_raises() -> None:
    section("D 未知 pooling → raise（不默认 cls）")
    import numpy as np

    last_hidden = np.ones((1, 3, 2), dtype=np.float32)
    mask = np.ones((1, 3), dtype=np.int64)
    for bad in ("", "max", "average", "none"):
        try:
            _pool_with(bad, last_hidden, mask)
            check(f"D[{bad!r}] 应 raise", False, "未抛异常")
        except RuntimeError as exc:
            check(f"D[{bad!r}] raise 且提示 pooling", "pooling" in str(exc), str(exc))


# ---------------------------------------------------------------------------
# E —— probe() 对未知 / 漏声明 pooling 判不可用
# ---------------------------------------------------------------------------
def _t_e_probe_rejects() -> None:
    section("E probe() 对未知/漏声明 pooling 判不可用")
    ok_rt, why = _have_runtime_deps()
    if not ok_rt:
        skip("E", why)
        return
    ok_res, why = _have_resource()
    if not ok_res:
        skip("E", why)
        return

    from app.core import embedder as emb_mod

    res, code, why = emb_mod.load_embedding_resource(RESOURCE_DIR)
    if not check("E0 资源可加载", res is not None, f"{code}: {why}"):
        return
    check("E1 随包清单显式声明受支持 pooling", res.pooling in ("cls", "mean"), res.pooling)

    # 漏声明 → pooling 落到空串 → probe 必须判不可用（走降级链）
    for bad in ("", "cosine"):
        bad_res = dataclasses.replace(res, pooling=bad)
        loaded, msg = emb_mod.OnnxEmbedder(bad_res).probe()
        check(f"E[{bad!r}] probe 判不可用", loaded is False, str(loaded))
        check(f"E[{bad!r}] 提示含 pooling 与降级",
              "pooling" in msg and "降级" in msg, msg)


# ---------------------------------------------------------------------------
# F —— 真实模型：mean 与 cls 不同，且 mean 与 numpy 手算 < 1e-6
# ---------------------------------------------------------------------------
def _t_f_real_model() -> None:
    section("F 真实模型 mean vs cls + 与 numpy 手算一致")
    ok_rt, why = _have_runtime_deps()
    if not ok_rt:
        skip("F", why)
        return
    ok_res, why = _have_resource()
    if not ok_res:
        skip("F", why)
        return

    import numpy as np

    from app.core import embedder as emb_mod

    res, code, why = emb_mod.load_embedding_resource(RESOURCE_DIR)
    if not check("F0 资源可加载", res is not None, f"{code}: {why}"):
        return

    texts = ["抽血化验之前得饿多长时间？",
             "基坑开挖深度约 17.6 米，监测频率为开挖阶段 1 次/天。"]

    emb_cls = emb_mod.OnnxEmbedder(dataclasses.replace(res, pooling="cls"))
    emb_mean = emb_mod.OnnxEmbedder(dataclasses.replace(res, pooling="mean"))
    ok1, w1 = emb_cls.probe()
    ok2, w2 = emb_mean.probe()
    if not check("F1 两个嵌入器 probe 通过", ok1 and ok2, f"cls={w1} mean={w2}"):
        return

    v_cls = np.asarray(emb_cls.embed(texts), dtype=np.float32)
    v_mean = np.asarray(emb_mean.embed(texts), dtype=np.float32)

    # 参考值：直接跑 session 手算（独立于 _pool）
    ref = _reference(emb_mean, texts, "mean")
    err = float(np.max(np.abs(v_mean - ref)))
    check("F2 mean 与 numpy 手算 < 1e-6", err < 1e-6, f"max={err:.2e}")
    check("F3 mean != cls（真实模型）",
          float(np.max(np.abs(v_mean - v_cls))) > 0.0,
          f"max={float(np.max(np.abs(v_mean - v_cls))):.3e}")
    check("F4 L2 归一化后范数≈1",
          all(abs(float(np.linalg.norm(v)) - 1.0) < 1e-5
              for v in list(v_mean) + list(v_cls)))


def _reference(emb, texts, mode):
    """直接调 session 手算池化结果（独立参照，不复用 _pool）。"""
    import numpy as np

    encs = emb._tok.encode_batch(list(texts))          # noqa: SLF001
    ids = np.array([e.ids for e in encs], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
    feed: dict = {}
    names = set(emb.io_names["inputs"])
    if "input_ids" in names:
        feed["input_ids"] = ids
    if "attention_mask" in names:
        feed["attention_mask"] = mask
    if "token_type_ids" in names:
        feed["token_type_ids"] = np.zeros_like(ids)
    outputs = emb._session.run(None, feed)             # noqa: SLF001
    last_hidden = None
    for name, arr in zip(emb.io_names["outputs"], outputs):
        if "last_hidden_state" in name.lower():
            last_hidden = arr
            break
    if last_hidden is None:
        last_hidden = [a for a in outputs if getattr(a, "ndim", 0) == 3][0]
    if mode == "mean":
        m = mask.astype(np.float32)[:, :, None]
        pooled = (last_hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
    else:
        pooled = last_hidden[:, 0, :]
    if emb.resource.normalize:
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        pooled = pooled / np.clip(norms, 1e-9, None)
    return np.asarray(pooled, dtype=np.float32)


def run_pooling_tests() -> None:
    from tests import test_env as _te

    _te.assert_test_library_safe()

    print("\n" + "=" * 66)
    print("  P0-0 —— pooling 修复单元测试")
    print("=" * 66)
    for label, fn in (
        ("A cls", _t_a_cls),
        ("B mean", _t_b_mean),
        ("C mean!=cls", _t_c_mean_differs),
        ("D 未知 raise", _t_d_unknown_raises),
        ("E probe 拒绝", _t_e_probe_rejects),
        ("F 真实模型", _t_f_real_model),
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - 单场景不得带崩套件
            check(f"P0-0 {label} 执行未抛异常", False, f"{type(exc).__name__}: {exc}")
    print(f"\n  P0-0 TOTAL={len(PASS) + len(FAIL) + len(SKIP)} "
          f"PASS={len(PASS)} SKIP={len(SKIP)} FAIL={len(FAIL)}")


if __name__ == "__main__":
    run_pooling_tests()
    raise SystemExit(1 if FAIL else 0)
