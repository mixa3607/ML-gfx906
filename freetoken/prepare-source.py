import pathlib
import sys
import tomllib


root = pathlib.Path(sys.argv[1])
project = root / "pyproject.toml"
text = project.read_text()
text = text.replace('torch>=2.14,<2.15', 'torch>=2.13,<2.14')
text = text.replace('torchvision>=0.29,<0.30', 'torchvision>=0.28,<0.29')
project.write_text(text)
dependencies = tomllib.loads(text)["project"]["dependencies"]
requirements = [dep for dep in dependencies if not dep.startswith(("torch", "triton"))]
requirements.extend(["setuptools>=77", "wheel", "ninja", "packaging"])
(root / "requirements-rocm.txt").write_text("\n".join(requirements) + "\n")
