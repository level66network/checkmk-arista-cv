NAME    := arista_cv
VERSION := $(shell python3 -c "import re; print(re.search(r'\"version\":\s*\"([^\"]+)\"', open('build_mkp.py').read()).group(1))")
MKP     := $(NAME)-$(VERSION).mkp

CVPRAC_VERSION := 2.1.0
CVPRAC_STAMP   := lib/python3/.cvprac-$(CVPRAC_VERSION)

CMK_ADDONS := cmk_addons_plugins/arista_cv/agent_based/arista_cv_devices.py \
              cmk_addons_plugins/arista_cv/agent_based/arista_cv_device_status.py \
              cmk_addons_plugins/arista_cv/agent_based/arista_cv_info.py \
              cmk_addons_plugins/arista_cv/rulesets/special_agent_arista_cv.py \
              cmk_addons_plugins/arista_cv/rulesets/check_params_arista_cv.py \
              cmk_addons_plugins/arista_cv/server_side_calls/special_agent_arista_cv.py

AGENTS  := agents/special/agent_arista_cv

VENDORED := lib/python3/cvprac/__init__.py \
            lib/python3/cvprac/cvp_api.py \
            lib/python3/cvprac/cvp_client.py \
            lib/python3/cvprac/cvp_client_errors.py

SOURCES := $(CMK_ADDONS) $(AGENTS) $(VENDORED)

.DEFAULT_GOAL := build

# ── Main targets ──────────────────────────────────────────────────────────────

.PHONY: build
build: $(MKP)

$(MKP): $(SOURCES) build_mkp.py
	python3 build_mkp.py

.PHONY: clean
clean:
	rm -f *.mkp
	rm -rf lib/

.PHONY: lint
lint:
	python3 -m py_compile $(SOURCES)
	@echo "Syntax OK"

# ── Vendor ────────────────────────────────────────────────────────────────────

.PHONY: vendor
vendor: $(CVPRAC_STAMP)

$(VENDORED): $(CVPRAC_STAMP)

$(CVPRAC_STAMP):
	@mkdir -p lib/python3/cvprac
	pip3 download "cvprac==$(CVPRAC_VERSION)" --no-deps -q -d /tmp/cvprac-$(CVPRAC_VERSION)
	python3 -c "\
import zipfile, pathlib, glob; \
whl = glob.glob('/tmp/cvprac-$(CVPRAC_VERSION)/cvprac-*.whl')[0]; \
z = zipfile.ZipFile(whl); \
dest = pathlib.Path('lib/python3'); \
[dest.joinpath(n).write_bytes(z.read(n)) for n in z.namelist() \
 if n.startswith('cvprac/') and n.endswith('.py')]"
	@touch $@

# ── Install (requires checkmk site user) ──────────────────────────────────────

.PHONY: install
install: $(MKP)
	mkp install $(MKP)
	cmk -R

.PHONY: uninstall
uninstall:
	mkp remove $(NAME) $(VERSION) || mkp remove $(NAME)

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo "Targets:"
	@echo "  build      Build $(MKP)  (default)"
	@echo "  vendor     Download and extract cvprac $(CVPRAC_VERSION) into lib/"
	@echo "  clean      Remove built .mkp files and vendored lib/"
	@echo "  lint       Syntax-check all Python source files"
	@echo "  install    Install and reload checkmk (run as site user)"
	@echo "  uninstall  Remove the installed package from checkmk"
