# Products.ExportImport -- development against the Plone 2.1 legacy image.
# Everything runs inside docker: there is no local Python 2.4.
#
# Recipes avoid .ONESHELL and other GNU Make >= 3.82 features: macOS ships 3.81.

IMAGE ?= plone/plone:2.1-demo
PLATFORM ?= linux/amd64
SITE_ID ?= Plone
PORT ?= 8080
# Data volume for `make start` / `make export`: keeps the site between runs.
VOLUME ?= exportimport-plone21-data

PRODUCT_DIR := $(CURDIR)/src/Products/ExportImport
EXPORT_DIR := $(CURDIR)/export
PRODUCT_MOUNT := -v $(PRODUCT_DIR):/app/instance/Products/ExportImport:ro
DOCKER_RUN := docker run --rm --platform $(PLATFORM) $(PRODUCT_MOUNT)
PYTHON24 := /opt/python2.4/bin/python2.4

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: start
start: ## Run Plone 2.1 with the product mounted (http://localhost:8080/Plone, admin/admin)
	@mkdir -p $(EXPORT_DIR)
	$(DOCKER_RUN) -it -p $(PORT):8080 \
		-v $(VOLUME):/data \
		-v $(EXPORT_DIR):/export -e EXPORTIMPORT_DIR=/export \
		$(IMAGE)

.PHONY: export
export: ## Export the site in the data volume to ./export (SITE_ID=, TYPES=; stop `make start` first)
	@mkdir -p $(EXPORT_DIR)
	@$(DOCKER_RUN) -v $(VOLUME):/data \
		-v $(EXPORT_DIR):/export -e EXPORTIMPORT_DIR=/export \
		-e SITE_ID=$(SITE_ID) -e EXPORTIMPORT_TYPES=$(TYPES) \
		$(IMAGE) run /app/instance/Products/ExportImport/scripts/export.py \
		> $(CURDIR)/export.log 2>&1; \
	grep -v 'DeprecationWarning\|^  ' $(CURDIR)/export.log | grep -v '^$$' | tail -20; \
	grep -q '^EXPORT-OK$$' $(CURDIR)/export.log

.PHONY: check
check: ## Check that every Python file compiles under Python 2.4
	docker run --rm --platform $(PLATFORM) --entrypoint $(PYTHON24) \
		-v $(CURDIR):/src:ro $(IMAGE) \
		/src/scripts/check_syntax.py /src/src /src/scripts

.PHONY: test
test: check ## Run the test suite inside the Plone 2.1 image
	@$(DOCKER_RUN) -w /app/instance $(IMAGE) /app/instance/bin/zopectl test \
		--dir Products/ExportImport $(TEST_ARGS) > $(CURDIR)/test.log 2>&1; \
	grep -v 'DeprecationWarning\|^  .*icon\|^$$' $(CURDIR)/test.log | tail -40; \
	grep -q '^Ran [1-9][0-9]* tests\{0,1\} in' $(CURDIR)/test.log && \
	grep -q '^OK' $(CURDIR)/test.log

.PHONY: clean
clean: ## Remove test and export logs
	rm -f $(CURDIR)/test.log $(CURDIR)/export.log

.PHONY: clean-data
clean-data: ## Delete the data volume: the site starts over from the demo database
	-docker volume rm $(VOLUME)
