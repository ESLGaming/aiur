aiur
====

Replay parser and analyzer for StarCraft 2, using the s2protocol library
released by Blizzard.

## Usage

### Getting the code

Aiur is a Python module, not a standalone program, so it needs to be imported
into another Python script. To use the module, clone the aiur git repository
to a subdirectory of the script that will use it. Aiur includes Blizzard's
s2protocol library as a submodule, so you also have to pull down the submodule
code. Once you have cloned the aiur repository, you can get the submodule code
by executing these commands in the repository directory:

```bash
$ git submodule init
$ git submodule update
```

### Using the module

You first need to import the module, then initialize an instance of the 
teSc2ReplayParser class with the path to an SC2Replay file.  The following
example script will open a replay file in the current directory and print the
name of the match winner to the console:

```python
from aiur import teSc2ReplayParser

parser = teSc2ReplayParser.teSc2ReplayParser("Antiga Shipyard.SC2Replay")
print parser.getMatchWinner()['m_name']
```

## License

This project is released under the 'Creative Commons Attribution-ShareAlike 3.0
Unported (CC BY-SA 3.0)' license. A short, human-readable summary can be found
here: http://creativecommons.org/licenses/by-sa/3.0/<br />
For the full license, please see the attached 'LICENSE' file.
