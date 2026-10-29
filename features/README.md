# Local features

Drop a `<name>.py` here with an `async def setup(bot)` and Rocko loads it as an add-on called
`<name>`. Rocko ships two this way: `lfg.py` (`/lfg`) and `teamkills.py` (`/tk`). Server admins can
turn them off like any add-on, and `ROCKO_DISABLED` in `.env` skips them on your PC.

It's the easy way to add something small. Anything you want other people to install on its own works
better as a package (see "Making an add-on" in the main README).
