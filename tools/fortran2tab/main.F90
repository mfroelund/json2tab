
PROGRAM main

    USE PARKIND1, ONLY : JPRB, JPIM
    IMPLICIT NONE

    INTEGER(KIND=JPIM)            :: WT_TYPE
    INTEGER(KIND=JPIM)            :: MAXSPEED
    REAL(KIND=JPRB),DIMENSION(50) :: CP ! power coefficient as function of wind speed m/s
    REAL(KIND=JPRB),DIMENSION(50) :: CT ! thrust coefficient as function of wind speed m/s
    REAL(KIND=JPRB)               :: RADROT ! radius of rotor [m]

    INTEGER(KIND=JPIM)            :: I
    INTEGER(KIND=JPIM)            :: FILETAG = 1


    CHARACTER(len=32) :: ARG
    CHARACTER(len=32) :: FILENAME
    CHARACTER(len=42) :: MANUFACTURER

    CALL GET_COMMAND_ARGUMENT(1, ARG)

    IF ( LEN_TRIM(ARG) == 0 ) THEN
        PRINT *, "Expected an integer-valued commandline argument to generate windturbine tab-file"
        CALL EXIT(-1_JPIM)
    END IF

    READ (ARG,'(I5)') WT_TYPE

    CALL WINDTURBINE_TYPE(WT_TYPE,CT,CP,MAXSPEED,RADROT)

    WRITE (FILENAME,'(A,I5.5,A)') "wind_turbine_FO_", WT_TYPE, ".tab"

    OPEN (UNIT=FILETAG, FILE=FILENAME, ACTION="WRITE")

    CALL GET_MANUFACTURER(WT_TYPE, MANUFACTURER)

    WRITE (FILETAG, '(A,A,A,I5.5,A,F4.0,A)') "# ", TRIM(MANUFACTURER), " FO_", WT_TYPE ," (z=00 m, D=", 2_JPRB * RADROT, " m)"

    WRITE (FILETAG, '(A,A,A,A,A,A,A,A)')  "#    ", "r (m)", "   ", "z (m)", "    ", "cT_low (-)", "    ", "cT_high (-)"
    WRITE (FILETAG, '(A,F8.4,A,A,A,F6.4,A,F6.4)')  "    ", RADROT, "   ", "0.0000", "    ", CT(MAXSPEED), "    ", CT(MAXSPEED)

    WRITE (FILETAG, '(A,A,A,A,A,A)')  "#    ", "U (m/s)", "   ", "cP (-)", "    ", "CT (-)"
    DO I = 1, MAXSPEED
        WRITE (FILETAG, '(A,I2,A,F6.4,A,F6.4)')  "    ", I, "   ", CP(I), "    ", CT(I)
    END DO

    CLOSE(FILETAG)

END PROGRAM main