MODULES = newhipc

all:	$(MODULES)

newhipc:	hipc.asm hipccode.asm
	vasm.vasmm68k-mot -no-opt -Fhunkexe -nosym -kick1hunks -I ../../score -o $@ $<

clean:
	rm -f $(MODULES)
