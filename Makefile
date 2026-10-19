# Thin front for `cargo xtask`, which does the work (and also runs without make on Windows).
.PHONY: help build install package lint fmt test smoke ci clean

help:
	@cargo xtask help

build install package lint fmt test smoke ci clean:
	cargo xtask $@
