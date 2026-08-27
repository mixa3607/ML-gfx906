CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11

vega20-rdi: vega20-rdi.c
	$(CC) $(CFLAGS) -o $@ $<

vega20-rdi-debugfs: vega20-rdi-debugfs.c vega20-rdi.c
	$(CC) $(CFLAGS) -o $@ vega20-rdi-debugfs.c
