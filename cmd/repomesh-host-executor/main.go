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
		fmt.Printf("repomesh-host-executor %s\n", buildinfo.Version)
		return
	}
	fmt.Fprintln(os.Stderr, "repomesh-host-executor: not implemented (scaffold only); no listener, host commands, containers or Python analysis are enabled")
	os.Exit(1)
}
