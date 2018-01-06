cd %~dp0\..\core

devcon.exe disable "PCI\VEN_1002&DEV_687F"

timeout /t 1

devcon.exe enable "PCI\VEN_1002&DEV_687F"

timeout /t 1

cd %~dp0\OverdriveN

OverdriveNTool.exe -p1test -p2test -p3test -p4test -p5test -p6test -p7test -p8test
