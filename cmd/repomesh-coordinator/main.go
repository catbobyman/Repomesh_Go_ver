package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"repomesh.local/repomesh/internal/access"
	"repomesh.local/repomesh/internal/buildinfo"
)

func main() { os.Exit(run()) }

func run() int {
	version := flag.Bool("version", false, "print release version and exit")
	config := flag.String("auth-config", os.Getenv("REPOMESH_AUTH_CONFIG"), "authentication deployment JSON file")
	flag.Parse()
	if *version {
		fmt.Printf("repomesh-coordinator %s\n", buildinfo.Version)
		return 0
	}
	if flag.NArg() != 0 {
		fmt.Fprintln(os.Stderr, "unexpected positional arguments")
		return 2
	}
	if *config == "" {
		fmt.Fprintln(os.Stderr, "repomesh-coordinator: authentication is not configured; no background work is running")
		return 1
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	startup, cancel := context.WithTimeout(ctx, 30*time.Second)
	runtime, err := access.OpenRuntime(startup, *config, os.Getenv("REPOMESH_DATABASE_URL"))
	cancel()
	if err != nil {
		fmt.Fprintln(os.Stderr, "coordinator startup:", err)
		return 1
	}
	defer runtime.Close()
	slog.Info("authentication coordinator started", "version", buildinfo.Version)
	for ctx.Err() == nil {
		work, cancel := context.WithTimeout(ctx, 15*time.Second)
		worked, err := runtime.Service.RunOne(work)
		cancel()
		if err != nil && ctx.Err() == nil {
			slog.Warn("authentication work deferred", "reason", err.Error())
		}
		delay := time.Second
		if worked && err == nil {
			delay = 100 * time.Millisecond
		}
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
		case <-timer.C:
		}
	}
	return 0
}
