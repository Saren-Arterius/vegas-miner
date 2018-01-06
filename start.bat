cd %~dp0\core

devcon.exe disable "PCI\VEN_1002&DEV_687F"

timeout /t 1

devcon.exe enable "PCI\VEN_1002&DEV_687F"

timeout /t 1

cd %~dp0\core\OverdriveN

OverdriveNTool.exe -p1mv915 -p2mv985 -p3mv975 -p4mv965 -p5mv915 -p6mv925 -p7mv965 -p8mv945

cd %~dp0\core\xmr-stak

xmr-stak.exe
