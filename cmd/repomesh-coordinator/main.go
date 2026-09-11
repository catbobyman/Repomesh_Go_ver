package main

import (
	"flag"
	"fmt"
	"os"

	"repomesh.local/repomesh/internal/buildinfo"
)

func main() {
	version := flag.Bool("version", false, "print release version and exit")
	flag.Parse()
	if *version {
		fmt.Printf("repomesh-coordinator %s\n", buildinfo.Version)
		return
	}
	fmt.Fprintln(os.Stderr, "repomesh-coordinator: not implemented (scaffold only); no queue, scheduling, Graph or AgentTeams integration is running")
	os.Exit(1)
}
