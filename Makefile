PYTHON ?= /usr/bin/python3

.PHONY: check package
check:
	PYTHON=$(PYTHON) ./scripts/check.sh

package:
	$(PYTHON) scripts/package.py
