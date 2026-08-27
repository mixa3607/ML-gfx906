GO ?= go

.PHONY: all test deb image

all: vega20-metrics

vega20-metrics:
	cd build-context && $(GO) build -o ../$@ ./cmd/vega20-metrics

test:
	cd build-context && $(GO) test ./...

deb:
	./build-and-push.deb.sh

image:
	./build-and-push.image.sh
