all: fortran2tab tabfiles

tabfiles: fortran2tab
	./convert.py fortran2tab
  
fortran2tab: parkind1.mod
	gfortran *.F90 -o fortran2tab


parkind1.mod:
	gfortran -c parkind1.F90

clean:
	rm -f *.o *.mod fortran2tab

cleanall: clean
	rm -f *.tab
