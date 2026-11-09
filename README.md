# supercon-nyan

A pop-tart cat for the Hackaday Supercon 2026 LED badge workshop panel
(Pimoroni Interstate 75 W + 64x64 HUB75 panel + MSA311 accelerometer).
It is a small 3D scene: the cat flies through a starfield and leaves a
rainbow trail behind it in the world, and you steer it by tilting the panel.
Made to hang off a backpack.

![preview](preview.png)

| Panel | Cat |
|---|---|
| hanging level | flies straight at you: its face, with a rainbow cone shrinking into the distance |
| top leaned back | flies away: you see its back, rainbow streaming toward you |
| tilted left / right | classic side view, flying that way |
| walking | every step bounces the cat, and the rainbow records the bounce |
| sharp jolt | sparkle burst and speed boost |

Neutral slowly follows however the panel is hanging, so it settles back to
flying at you. Button **A** cycles brightness, **B** fires sparkles.

## Install on your badge

It only needs the `interstate75` and `msa311.py` files the workshop board
already has, plus this one file.

1. Copy `nyan.py` to the board (Thonny: open it, *Save as...* > *Raspberry Pi
   Pico*; or `mpremote cp nyan.py :nyan.py`).
2. Try it: run `nyan.py` from Thonny, or `mpremote run nyan.py`.
3. To start it at power-on, add this to `main.py` right after `i75` is created
   (here: only when A and B are held during boot, so your normal show still runs):

   ```python
   if i75.switch_pressed(0) and i75.switch_pressed(1):
       import nyan
       nyan.run(i75)            # forever; nyan.run(i75, 90) returns after 90 s
   ```

   Or drop the `if` to make it the default.

If it steers the wrong way on your panel, flip `TILT_SIGN` (left/right) or
`DEPTH_SIGN` (toward/away) at the top of `nyan.py`. `BOUNCE` sets how hard
your steps bounce it.

### Faster (optional)

MicroPython 1.29 on the RP2350 can load precompiled bytecode, which starts quicker
and uses less RAM:

```sh
pip install mpy-cross mpremote
mpy-cross -march=armv7emsp nyan.py
mpremote cp nyan.mpy :nyan.mpy + rm :nyan.py
```

(MicroPython picks `nyan.py` over `nyan.mpy`, so remove the `.py`.)

## Preview on a computer

```sh
pip install pillow
python3 tools/sim_nyan.py      # writes preview.png from a scripted tilt/walk
```

## License

MIT
