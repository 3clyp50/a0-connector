# a0-computer-use-x11

Xorg/X11 computer-use backend for `a0`.

The backend uses XTEST through `python-xlib` for mouse and keyboard input, and
`mss` for screen capture. It is selected automatically on Linux when an X11
display is available and the session is not Wayland.
