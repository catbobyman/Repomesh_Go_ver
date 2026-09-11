package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"repomesh.local/repomesh/internal/buildinfo"
	"repomesh.local/repomesh/internal/web"
)

func main() {
	addr := flag.String("addr", envOr("REPOMESH_WEB_ADDR", "127.0.0.1:8080"), "HTTP listen address")
	assets := flag.String("assets", envOr("REPOMESH_WEB_ASSETS", "web/dist"), "built frontend directory (relative to working directory)")
	version := flag.Bool("version", false, "print release version and exit")
	flag.Parse()
	if *version {
		fmt.Printf("repomesh-web %s\n", buildinfo.Version)
		return
	}
	if flag.NArg() != 0 {
		slog.Error("unexpected positional arguments")
		os.Exit(2)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := web.Run(ctx, *addr, *assets); err != nil {
		slog.Error("web stopped", "error", err)
		os.Exit(1)
	}
}

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
