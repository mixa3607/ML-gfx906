GO ?= go

all: vega20-metrics

vega20-metrics:
	$(GO) build -o $@ ./cmd/vega20-metrics

test:
	$(GO) test ./...
