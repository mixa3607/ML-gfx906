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

	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/config"
	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/gpu"
	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/observe"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func main() {
	configPath := flag.String("config", config.DefaultPath, "configuration file path")
	flag.Parse()
	runtimeConfig, err := config.Load(*configPath)
	if err != nil {
		log.Fatalf("load configuration: %v", err)
	}

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

	collector, err := gpu.NewCollector(runtimeConfig.Sysfs, runtimeConfig.RegisterBackend, runtimeConfig.VBIOS, runtimeConfig.Devices.VendorProducts, runtimeConfig.Devices.PCIDevices)
	if err != nil {
		log.Fatalf("configure GPU collector: %v", err)
	}
	registry := prometheus.NewRegistry()
	registry.MustRegister(collector)
	server := &http.Server{
		Addr:              runtimeConfig.Listen,
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

	log.Printf("serving Prometheus metrics on %s", runtimeConfig.Listen)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
