package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/gpu"
	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/observe"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func main() {
	listen := flag.String("listen", ":9487", "HTTP listen address")
	sysfs := flag.String("sysfs", "/sys", "sysfs root")
	backend := flag.String("register-backend", "debugfs", "register backend: debugfs, bar5, or none")
	vbios := flag.String("vbios", "", "VBIOS ROM used for calibrated SVI2 current")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	shutdown, err := observe.Init(ctx)
	if err != nil {
		log.Fatalf("configure OpenTelemetry: %v", err)
	}
	defer func() {
		if err := shutdown(context.Background()); err != nil {
			log.Printf("shutdown OpenTelemetry: %v", err)
		}
	}()

	collector, err := gpu.NewCollector(*sysfs, *backend, *vbios)
	if err != nil {
		log.Fatalf("configure GPU collector: %v", err)
	}
	registry := prometheus.NewRegistry()
	registry.MustRegister(collector)
	server := &http.Server{
		Addr:              *listen,
		Handler:           promhttp.HandlerFor(registry, promhttp.HandlerOpts{}),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("shutdown HTTP server: %v", err)
		}
	}()

	log.Printf("serving Prometheus metrics on %s", *listen)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
