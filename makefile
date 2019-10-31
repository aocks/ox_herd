
.PHONY: pypi help test

help:
	@echo "This is a makefile to push to pypi."
	@echo "Use make pypi to push to pypi."

test:
	py.test --doctest-modules tests ox_herd

pypi: README.rst test
	 python3 setup.py sdist upload -r pypi

README.rst: README.md
	pandoc --from=markdown --to=rst --output=README.rst README.md

