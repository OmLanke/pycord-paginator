from setuptools import setup
import re

version = ""
with open("discord/ext/paginator/__init__.py") as f:
    version = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE
    ).group(1)

if not version:
    raise RuntimeError("version is not set")

if version.endswith(("a", "b", "rc")):
    # append version identifier based on commit count
    try:
        import subprocess

        p = subprocess.Popen(
            ["git", "rev-list", "--count", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += out.decode("utf-8").strip()
        p = subprocess.Popen(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += "+g" + out.decode("utf-8").strip()
    except Exception:
        pass

setup(
    name="pycord-paginator",
    author="Om Lanke",
    url="https://github.com/Om1609/pycord-paginator",
    version=version,
    packages=["discord.ext.paginator"],
    license="MIT",
    description="A cool fork of Py-cord's paginator.",
    #   install_requires=['py-cord>=2.4.0'],
    python_requires=">=3.8.0",
)
