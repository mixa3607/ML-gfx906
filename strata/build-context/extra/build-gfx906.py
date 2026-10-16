"""Compile the gfx906 engine during image build.

This is the cmake recipe that already builds in ML-gfx906/strata/build-local.Dockerfile.
llama.cpp is downloaded from GitHub at the commit pinned in setup.py.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/opt/strata")
sys.path.insert(0, str(ROOT))
import setup

if setup.ROOT != ROOT:
    raise SystemExit(f"setup.py resolved to {setup.ROOT}, expected {ROOT}")

rocm = Path("/opt/rocm")
clangxx = rocm / "llvm" / "bin" / "clang++"
if not clangxx.is_file() or not (rocm / "bin" / "hipcc").is_file():
    raise SystemExit("the ROCm image has no hipcc or clang++; use rocm-gfx906:<ver>-complete")
bitcode = next((p for p in (
    rocm / "lib" / "llvm" / "amdgcn" / "bitcode",
    rocm / "amdgcn" / "bitcode",
) if p.is_dir()), None)
if bitcode is None:
    raise SystemExit("the ROCm image has no amdgcn bitcode directory")

llama = setup.get_llama_cpp()
build = ROOT / "build-906"
setup.cmake_build(ROOT, build, "strata", [
    "-DSTRATA_HIP_GFX906=ON",
    "-DSTRATA_ENABLE_HIP=OFF",
    "-DSTRATA_BUILD_TESTS=OFF",
    "-DSTRATA_PORTABLE=ON",
    "-DCMAKE_HIP_ARCHITECTURES=gfx906",
    f"-DSTRATA_GGML_DIR={llama}",
    f"-DCMAKE_C_COMPILER={rocm / 'llvm' / 'bin' / 'clang'}",
    f"-DCMAKE_CXX_COMPILER={clangxx}",
    f"-DCMAKE_HIP_COMPILER={clangxx}",
    f"-DCMAKE_HIP_COMPILER_ROCM_ROOT={rocm}",
    f"-DCMAKE_PREFIX_PATH={rocm}",
    f"-DCMAKE_HIP_FLAGS=--rocm-path={rocm} --rocm-device-lib-path={bitcode}",
], None, "")

built = build / setup.EXE
if not built.is_file():
    raise SystemExit(f"gfx906 engine was not produced: {built}")
engine = ROOT / "engine"
engine.mkdir(exist_ok=True)
shutil.copy2(built, engine / setup.EXE)
(engine / setup.EXE).chmod(0o755)
meta = {
    "source": "local-hip",
    "backend": "hip",
    "version": setup.source_version(),
    "archs": ["gfx906"],
    "vision": "none",
    "lib_dirs": [str(rocm / "lib")],
    "src": setup.source_hash(setup.ENGINE_SOURCES),
}
(engine / "BUILD.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
shutil.rmtree(build, ignore_errors=True)
