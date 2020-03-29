from datetime import datetime
import hashlib

# Library to read Blizzards MPYQ files
import mpyq

# sc2 replay protocols
from s2protocol import versions

#
#  Currently provides these methods/data:
#  - Get the match winner
#  - Get a match object containing several information of the match
class teBlizzardReplayParser:
    replayHeader = {}
    replayDetails = {}
    replayInitData = {}
    replayGameEvents = []
    replayMessageEvents = []
    replayTrackerEvents = []
    replayAttributeEvents = []

    # Events counting into the APM of a player
    apmEvents = ['NNet.Game.SSelectionDeltaEvent',
                 'NNet.Game.SCmdEvent',
                 'NNet.Game.SControlGroupUpdateEvent'
                 # 'NNet.Game.SGameUserLeaveEvent',
                 # 'NNet.Game.STriggerPortraitLoadedEvent',
                 # 'NNet.Game.SCameraUpdateEvent',
                 # 'NNet.Game.SCameraSaveEvent'
                ]
    # Mapping of gamespeed indentifiers
    gamespeeds = {0: 'Slower',
                  1: 'Slow',
                  2: 'Normal',
                  3: 'Fast',
                  4: 'Faster'}

    # Mapping of region codes
    regionCodes = {1: 'us', # us.battle.net
                   2: 'eu', # eu.battle.net
                   3: 'kr', # kr.battle.net
                   5: 'cn', # cn.battle.net
                   6: 'sea'} # sea.battle.net

    # "Constants"
    PLAYER_CONTROL_HUMAN = 2
    PLAYER_CONTROL_AI = 3
    PLAYER_OBSERVE_IS_NO_OBSERVER = 0
    PLAYER_OBSERVE_IS_OBSERVER = 1
    PLAYER_OBSERVE_IS_HOST = 2
    RESULT_WINNER = 1
    RESULT_LOSER = 2

    GAME_PROTOCOLS = {
        "sc2" : {
            "protocol":  "s2protocol",
            "programId": "S2"
        },
        "hero": {
            "protocol":  "heroprotocol",
            "programId": "Hero"
        }
    }


    ## Constructor of teBlizzardReplayParser.
    #
    #  Creates an instance of the mpq-archive reader, reads the replay header
    #  to find out the base build of the replay and therefore load the correct
    #  protocol version. Will raise an exception if the basebuild is unknown.
    #
    #  Fallback to sc2 for backward compatible reasons
    def __init__(self, replayFilename, game="sc2"):
        if game not in self.GAME_PROTOCOLS:
            raise UnknownGameException(game)

        self.game = game
        self.replayFilename = replayFilename
        self.mpqArchive = mpyq.MPQArchive(self.replayFilename)

        # The header's baseBuild determines which protocol to use (this works with every version)
        baseBuild = self.getHeader()['m_version']['m_baseBuild']
        packageName = self.GAME_PROTOCOLS[game]["protocol"]
        if __package__ is not None:
            packageName = '%s.%s' % (__package__, packageName)
        try:
            # Will raise an ImportError-exception if the basebuild is unknown
            self.protocol = versions.build(baseBuild)
        except ImportError:
            raise UnknownBaseBuildException(baseBuild)


    def getHeader(self):
        if len(self.replayHeader) <= 0:
            # Read the protocol header, this can be read with any protocol
            self.replayHeader = versions.latest().decode_replay_header(self.mpqArchive.header['user_data_header']['content'])

        return self.replayHeader

    def getDetails(self):
        if len(self.replayDetails) <= 0:
            self.replayDetails = self.protocol.decode_replay_details(self.mpqArchive.read_file('replay.details'))

            # Some old replays also (adidtionally to the initData) have these senseless cache_handles including invalid unicode chars
            # del self.replayDetails['m_cacheHandles']

        return self.replayDetails

    def getInitData(self):
        if len(self.replayInitData) <= 0:
            self.replayInitData = self.protocol.decode_replay_initdata(self.mpqArchive.read_file('replay.initData'))
            # Drop these senseless cache_handles including invalid unicode chars
            del self.replayInitData['m_syncLobbyState']['m_gameDescription']['m_cacheHandles']

        return self.replayInitData

    def getGameEvents(self):
        if len(self.replayGameEvents) <= 0:
            # This returns only a generator, we have to iterate through it to get all the events
            gameGenerator = self.protocol.decode_replay_game_events(self.mpqArchive.read_file('replay.game.events'))
            for event in gameGenerator:
                self.replayGameEvents.append(event)

        return self.replayGameEvents

    def getMessageEvents(self):
        if len(self.replayMessageEvents) <= 0:
            # This returns only a generator, we have to iterate through it to get all the events
            messageGenerator = self.protocol.decode_replay_message_events(self.mpqArchive.read_file('replay.message.events'))
            for event in messageGenerator:
                self.replayMessageEvents.append(event)

        return self.replayMessageEvents

    def getTrackerEvents(self):
        if len(self.replayTrackerEvents) <= 0:
            # This returns only a generator, we have to iterate through it to get all the events
            trackerGenerator = self.protocol.decode_replay_tracker_events(self.mpqArchive.read_file('replay.tracker.events'))
            for event in trackerGenerator:
                if event.has_key('m_unitTagIndex') and event.has_key('m_unitTagRecycle'):
                    # Directky generate the unit_tag, as we will need it anyways.
                    event['_unit_tag'] = self.protocol.unit_tag(event['m_unitTagIndex'], event['m_unitTagRecycle'])
                self.replayTrackerEvents.append(event)

        return self.replayTrackerEvents

    def getAttributeEvents(self):
        if len(self.replayAttributeEvents) <= 0:
            self.replayAttributeEvents = self.protocol.decode_replay_attributes_events(self.mpqArchive.read_file('replay.attributes.events'))

        return self.replayAttributeEvents

    ## Remove some HTML from a string.
    #
    #  Remove known HTML which appears in strings. Currently:
    #  <sp/>
    #
    #  @param self   The object pointer.
    #  @param string The string to remove the HTML from.
    #
    #  @return string The tydied string.
    def stripHtmlFromString(self, string):
        if not isinstance(string,str):
            string = string.decode('utf-8')

        return string.replace('<sp/>', ' ')

    ## Remove zero bytes (\x00) from a string.
    #
    #  Some strings contain zero bytes which destroys the string
    #
    #  @param self   The object pointer.
    #  @param string The string to remove the zero bytes from.
    #
    #  @return string The tydied string.
    def stripZeroBytesFromString(self, string):
        if not isinstance(string,str):
            string = string.decode('utf-8')

        return string.strip(u'\u0000')

    ## Convert a Windows NT timestamp to a UNIX timestamp.
    #
    #  Windows has it's own timestamp format and Blizzard uses it. This method
    #  decodes this timestamp using a tutorial linked in the @see.
    #
    #  @param self        The object pointer.
    #  @param ntTimestamp The Windows NT timestamp to convert.
    #
    #  @see http://support.citrix.com/article/CTX109645
    #
    #  @return int The UNIX timestamp for the given NT timestamp.
    def convertWindowsNtTimestampToUnixTimestamp(self, ntTimestamp):
        return int((ntTimestamp / 10000000) - 11644473600)
        # Alternative way would be to substract the 100 nanoseconds since
        # 1601-01-01 and convert it to seconds:
        # (ntTimestamp - 134774 * 24 * 60 * 60 * 10**7) / 10**7
        # return int((ntTimestamp - 116444736000000000) / 10**7)

    ## Convert the timezone offset from nanoseconds to hours.
    #
    #  The timezone offset is stored as 100 nanosends, so for example UTC+2
    #  would be 2 * 60*60*10^7 = 72000000000.
    #
    #  @param self        The object pointer.
    #  @param ntTimestamp The UTC timezone offset in 100 nanoseconds
    #
    #  @return int The UTC timezone offset in hours
    def convertTimezoneOffsetToUtcTimezone(self, timezoneOffset):
        # 60*60*10^7 = 36000000000
        return timezoneOffset / 36000000000

    ## Returns the player-dict for a given toon.
    #
    #  Steps through all players and immediately stops and returns the player
    #  for the given toon. The toon seems to be the battlenet-worldwide-unique
    #  identifier of a player.
    #
    #  @param self The object pointer.
    #  @param toon The unique identifier to find the player for.
    #
    #  @return dict|None The player dict or None if not found.
    def getPlayerEntryForToon(self, toon):
        playersList = self.getDetails()['m_playerList']
        for i, player in enumerate(playersList):
            # There are invalid chars (0bytes or sth) in these strings. so strip them before and convert it back from unicode- to regular string
            player['m_toon']['m_programId'] = self.stripZeroBytesFromString(player['m_toon']['m_programId'])

            playerToon = str(player['m_toon']['m_region']) + '-' + player['m_toon']['m_programId'] + '-' + str(player['m_toon']['m_realm']) + '-' + str(player['m_toon']['m_id'])
            if playerToon == toon:
                player['m_playerId'] = i + 1
                return player;

        return None

    ## Returns the player-dict for a given workingSetSlotId.
    #
    #  Steps through all players and immediately stops and returns the player
    #  for the given workingSetSlotId.
    #
    #  @param self The object pointer.
    #  @param toon The workingSetSlotId to find the player for.
    #
    #  @return dict|None The player dict or None if not found.
    def getPlayerEntryForSlotId(self, slotId):
        playersList = self.getDetails()['m_playerList']
        for i, player in enumerate(playersList):
            # There are invalid chars (0bytes or sth) in these strings. so strip them before and convert it back from unicode- to regular string
            player['m_toon']['m_programId'] = self.stripZeroBytesFromString(player['m_toon']['m_programId'])

            if player['m_workingSetSlotId'] == slotId:
                player['m_playerId'] = i + 1
                return player;

        return None


    ## Returns the player-dict who has won the match.
    #
    #  Steps through all players and immediately stops and returns the player
    #  when found.
    #
    #  @param self The object pointer.
    #
    #  @return dict|None The winning player dict or None if not found.
    def getMatchWinner(self):
        playersList = self.getDetails()['m_playerList']
        for player in playersList:
            if player['m_result'] == self.RESULT_WINNER:
                return player

        return None

    ## Returns the match size / game mode (XonX).
    #
    #  Looks up the special attribute scope 16, containing general match
    #  attributes, and looks for attribute 2001, the match size.
    #
    #  @param self The object pointer.
    #
    #  @return string|None The match size in format 'XvX' or None if not found.
    def getGameMode(self):
        attributeEvents = self.getAttributeEvents()

        if 16 in attributeEvents['scopes']:
            if 2001 in attributeEvents['scopes'][16]:
                return attributeEvents['scopes'][16][2001][0]['value']

        return None

    ## Tries to generate a unique md5 hash, like a matchId.
    #
    #  This hash tries to be a battlenet-matchId replacement, but is NOT
    #  guaranteed to be globally unique!
    #  But it's unique enough to determine the rounds of a bestOfX match for
    #  example. That means that every replay from any participant (player,
    #  observer, etc.) of a single match generates the same hash, so you
    #  know which replays belong to one match and therefore for one round
    #  in a bestOfX match.
    #  For generating the hash, the userIds assigned to the toonHandles of every
    #  player is used, plus the randomSeed, which is randomly generated per
    #  match, but is not unique!
    #
    #  @param self The object pointer.
    #  @param players The list of players, generated by self.getMatchDetails()
    #
    #  @return string The generated replayHash
    def generateReplayHash(self, players):
        initData = self.getInitData()
        hashData = []

        # Iterate over our playerList and concatinate the userId with the
        # toonHandle
        for key, player in players['humans'].items():
            hashData.append(str(player['user_id']) + ':' + str(player['toon']['handle']))
        # Also append the randomSeed, which makes it kinda "unique"
        hashData.append(str(initData['m_syncLobbyState']['m_lobbyState']['m_randomSeed']))

        # Hash our data with the md5 algorithm and return it
        return hashlib.md5(';'.join(hashData).encode('utf-8')).hexdigest()

    ## Returns the match document incl. various information about the match.
    #
    #  Builds the match document with the list of players, observers, computers,
    #  map name, the matcwinner, duration, matchtime, etc...
    #
    #  @param self The object pointer.
    #
    #  @return dict The match document.
    def getMatchDetails(self):
        details = self.getDetails()
        header = self.getHeader()
        initData = self.getInitData()

        playersInLobby = initData['m_syncLobbyState']['m_userInitialData']
        slots = initData['m_syncLobbyState']['m_lobbyState']['m_slots']

        players = {'humans': {},
                   'computers': {}}
        observers = {}
        teams = []
        matchWinnerToon = -1
        matchWinnerTeam = -1
        # TODO: This loop may need some refactoring to make it less complex (e.g. too much if/else)!
        for slot in slots:
            # AIs don't have a userId, so we have to get the playername via the playerList
            if slot['m_control'] == self.PLAYER_CONTROL_AI:
                player = self.getPlayerEntryForSlotId(slot['m_workingSetSlotId'])
                playerName = self.stripHtmlFromString(player['m_name'] if player['m_name'] else '')
                clanTag = ''
                userId = -1
                # AIs also don't have a toon, but we need them! So generate an 'invalid' one out of the playerId
                toonHandle = '0-' + str(self.GAME_PROTOCOLS[self.game]["programId"]) + '-0-' + str(player['m_playerId'])
            elif slot['m_userId'] != None:
                userId = slot['m_userId']
                playerName = self.stripHtmlFromString(playersInLobby[userId]['m_name'] if playersInLobby[userId]['m_name'] else '')
                clanTag = self.stripHtmlFromString(playersInLobby[userId]['m_clanTag'] if playersInLobby[userId]['m_clanTag'] else '')
                toonHandle = slot['m_toonHandle']
            else:
                continue

            # Create a dict containg information for every type of user
            data = {'user_id': userId,
                    #Some kind of a unique identifier
                    'toon': {'handle': toonHandle},
                    'name': playerName,
                    'clan_tag': clanTag,
                    'fullname': (('[' + clanTag + ']') if len(clanTag) > 0 else '') + playerName,
                    'team_id': slot['m_teamId']}

            # Collect all teamIDs
            if not data['team_id'] in teams:
                teams.append(data['team_id'])

            if slot['m_observe'] > self.PLAYER_OBSERVE_IS_NO_OBSERVER:
                observers[toonHandle] = data
            else:
                player = self.getPlayerEntryForSlotId(slot['m_workingSetSlotId'])

                # Something strange happend: The user is not in the playerslist!
                if player == None:
                    continue

                # Is this the matchwinner (for team matches, the toonHandle doesn't matter)?
                if player['m_result'] == self.RESULT_WINNER:
                    matchWinnerToon = toonHandle
                    matchWinnerTeam = data['team_id']

                data.update({'player_id': player['m_playerId'],
                             'toon': dict(list(data['toon'].items()) + list({'programId': player['m_toon']['m_programId'],
                                                                  'region': player['m_toon']['m_region'],
                                                                  'id': player['m_toon']['m_id'],
                                                                  'realm': player['m_toon']['m_realm']}.items())),
                             'race': player['m_race'].decode('utf-8'),
                             'result': player['m_result'],
                             'color': {'r': player['m_color']['m_r'],
                                       'g': player['m_color']['m_g'],
                                       'b': player['m_color']['m_b'],
                                       'a': player['m_color']['m_a']
                            }})

                if slot['m_control'] == self.PLAYER_CONTROL_AI:
                    players['computers'][toonHandle] = data
                else:
                    players['humans'][toonHandle] = data

        gameMode = self.getGameMode()
        # Fallback, if the attribute couldn't be found
        if not gameMode:
            playersPerTeam = len(players['humans']) / len(teams)
            gameMode = '%dv%d' % (playersPerTeam, playersPerTeam)

        return {'mapname': details['m_title'].decode("utf-8"),
                'replay_hash': self.generateReplayHash(players),
                'started_at': datetime.fromtimestamp(self.convertWindowsNtTimestampToUnixTimestamp(details['m_timeUTC'])).strftime('%Y-%m-%d %H:%M:%S'),
                'utc_timezone': self.convertTimezoneOffsetToUtcTimezone(details['m_timeLocalOffset']),
                'duration': round(header['m_elapsedGameLoops'] / 16),
                'winner_toon_handle': matchWinnerToon,
                'winner_team_id': matchWinnerTeam,
                'version': {'number': str(header['m_version']['m_major']) + '.' + str(header['m_version']['m_minor']) + '.' + str(header['m_version']['m_revision']),
                            'build': header['m_version']['m_build']},
                'gamemode': gameMode.decode("utf-8"),
                'gamespeed': self.gamespeeds[initData['m_syncLobbyState']['m_gameDescription']['m_gameSpeed']],
                'host_user_id': initData['m_syncLobbyState']['m_lobbyState']['m_hostUserId'] or -1,
                'players': players,
                'observers': observers}
# End class teBlizzardReplayParser

class UnknownBaseBuildException(Exception):
    def __init__(self, baseBuild):
        self.baseBuild = baseBuild

    def __str__(self):
        return 'Unsupported base build %d' % self.baseBuild

class UnknownGameException(Exception):
    def __init__(self, game):
        self.game = game

    def __str__(self):
        return 'Unsupported game %s' % self.game
