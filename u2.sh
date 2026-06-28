mpremote exec "import os; os.mkdir('drivers')" 2>/dev/null || true
mpremote exec "import os; os.mkdir('drivers/ili93xx')" 2>/dev/null || true
mpremote cp boolpalette.py :drivers/boolpalette.py
mpremote cp ili9341.py     :drivers/ili93xx/ili9341.py
mpremote run chess_clock.py
