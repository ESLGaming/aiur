aiur
====

Replay parser and analyser for Blizzard Replays, using the s2protocol and heroprotocol released by Blizzard

## Usage

### Getting the code

Aiur is a Python module, not a standalone program, so it needs to be imported
into another Python script. To use the module, clone the aiur git repository
to a subdirectory of the script that will use it. Aiur includes Blizzard's
s2protocol and heroprotocol library as a submodule, so you also have to pull down the submodule
code. Once you have cloned the aiur repository, you can get the submodule code
by executing these commands in the repository directory:

```bash
$ git submodule init
$ git submodule update
```

### Using the module

You first need to import the module, then initialize an instance of the 
teBlizzardReplayParser class with the path to and the game of a replay file.  The following
example script will open a SC2 replay file in the current directory and print the
name of the match winner to the console:

```python
from aiur import teBlizzardReplayParser

parser = teBlizzardReplayParser.teBlizzardReplayParser("Antiga Shipyard.SC2Replay", "sc2")
print parser.getMatchWinner()['m_name']
```

## License

This project is released under the 'Creative Commons Attribution-ShareAlike 3.0
Unported (CC BY-SA 3.0)' license. A short, human-readable summary can be found
here: http://creativecommons.org/licenses/by-sa/3.0/<br />
For the full license, please see the attached 'LICENSE' file.