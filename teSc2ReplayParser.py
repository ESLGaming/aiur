from datetime import datetime

# Library to read Blizzards MPYQ files
from s2protocol.mpyq import mpyq
# Import the oldest protocol to read the replay header, which works with every
# replay version
from s2protocol import protocol15405


## Evaluates sc2replays and provides several methods to get data out of it.
#
#  Currently provides these methods/data:
#  - Get the match winner
#  - Get a match object containing several information of the match
class teSc2ReplayParser:
    replayHeader = {}
    replayDetails = {}
    replayInitData = {}
    replayGameEvents = []
    replayMessageEvents = []
    replayTrackerEvents = []
    replayAttributeEvents = {}

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
    regionCodes = {1: 'us',
                   2: 'eu',
                   3: 'kr'}

    # "Constants"
    PLAYER_CONTROL_HUMAN = 2
    PLAYER_CONTROL_AI = 3
    PLAYER_OBSERVE_IS_NO_OBSERVER = 0
    PLAYER_OBSERVE_IS_OBSERVER = 1
    PLAYER_OBSERVE_IS_HOST = 2
    RESULT_WINNER = 1
    RESULT_LOSER = 2


    ## Constructor of teSc2ReplayParser.
    #
    #  Creates an instance of the mpq-archive reader, reads the replay header
    #  to find out the base build of the replay and therefore load the correct
    #  protocol version. Will raise an exception if the basebuild is unknown.
    def __init__(self, replayFilename):
        self.replayFilename = replayFilename
        self.mpqArchive = mpyq.MPQArchive(self.replayFilename)

        # The header's baseBuild determines which protocol to use (this works with every version)
        baseBuild = self.getHeader()['m_version']['m_baseBuild']
        packageName = 's2protocol'
        if len(__package__) > 0:
            packageName = '%s.%s' % (__package__, packageName)

        try:
            # Will raise an ImportError-exception if the basebuild is unknown
            self.protocol = __import__(packageName + '.protocol%s' % baseBuild, fromlist=[packageName])
        except ImportError:
            raise UnknownBaseBuildException(baseBuild)


    def getHeader(self):
        if len(self.replayHeader) <= 0:
            # Read the protocol header, this can be read with any protocol
            self.replayHeader = protocol15405.decode_replay_header(self.mpqArchive.header['user_data_header']['content'])

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
        return string.replace('<sp/>', ' ')

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
            player['m_toon']['m_programId'] = str(player['m_toon']['m_programId'].strip(u'\u0000'))

            playerToon = str(player['m_toon']['m_region']) + '-' + player['m_toon']['m_programId'] + '-' + str(player['m_toon']['m_realm']) + '-' + str(player['m_toon']['m_id'])
            if playerToon == toon:
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

        playersList = details['m_playerList']
        playersInLobby = initData['m_syncLobbyState']['m_userInitialData']
        slots = initData['m_syncLobbyState']['m_lobbyState']['m_slots']

        players = {}
        observers = {}
        computers = {}
        matchWinner = -1
        for slot in slots:
            if slot['m_userId'] == None:
                continue;

            userId = slot['m_userId']
            playerName = self.stripHtmlFromString(playersInLobby[userId]['m_name'])
            clanTag = self.stripHtmlFromString(playersInLobby[userId]['m_clanTag']);
            data = {'user_id': userId,
                    #Some kind of a unique identifier
                    'toon': {'handle': slot['m_toonHandle']},
                    'name': playerName,
                    'clan_tag': clanTag,
                    'fullname': (('[' + clanTag + ']') if len(clanTag) > 0 else '') + playerName,
                    'team_id': slot['m_teamId']}

            if slot['m_observe'] > self.PLAYER_OBSERVE_IS_NO_OBSERVER:
                observers[str(userId)] = data
            elif slot['m_control'] == self.PLAYER_CONTROL_AI:
                computers[str(userId)] = data
            else:
                player = self.getPlayerEntryForToon(slot['m_toonHandle'])

                # Something strange happend: The user is not in the playerslist!
                if player == None:
                    continue

                playerId = player['m_playerId']

                if player['m_result'] == self.RESULT_WINNER:
                    matchWinner = player['m_playerId']

                data.update({'player_id': playerId,
                             'bnet_id': player['m_toon']['m_id'],
                             'toon': dict(data['toon'].items() + {'programId': player['m_toon']['m_programId'],
                                                                  'region': player['m_toon']['m_region'],
                                                                  'id': player['m_toon']['m_id'],
                                                                  'realm': player['m_toon']['m_realm']}.items()),
                             'race': player['m_race'],
                             'result': player['m_result'],
                             'color': {'r': player['m_color']['m_r'],
                                       'g': player['m_color']['m_g'],
                                       'b': player['m_color']['m_b'],
                                       'a': player['m_color']['m_a']
                            }})
                players[str(playerId)] = data

        playersPerTeam = int(initData['m_syncLobbyState']['m_gameDescription']['m_maxUsers'] / initData['m_syncLobbyState']['m_gameDescription']['m_maxTeams'])

        return {'mapname': details['m_title'],
                'started_at': datetime.fromtimestamp(self.convertWindowsNtTimestampToUnixTimestamp(details['m_timeUTC'])).strftime('%Y-%m-%d %H:%M:%S'),
                'utc_timezone': self.convertTimezoneOffsetToUtcTimezone(details['m_timeLocalOffset']),
                'duration': round(header['m_elapsedGameLoops'] / 16),
                'winner_player_id': matchWinner,
                'version': {'number': str(header['m_version']['m_major']) + '.' + str(header['m_version']['m_minor']) + '.' + str(header['m_version']['m_revision']),
                            'build': header['m_version']['m_build']},
                'gamemode': str(playersPerTeam) + 'v' + str(playersPerTeam),
                'gamespeed': self.gamespeeds[initData['m_syncLobbyState']['m_gameDescription']['m_gameSpeed']],
                'host_user_id': initData['m_syncLobbyState']['m_lobbyState']['m_hostUserId'],
                'players': players,
                'observers': observers,
                'computers': computers}
# End class teSc2ReplayParser

class UnknownBaseBuildException(Exception):
    def __init__(self, baseBuild):
        self.baseBuild = baseBuild

    def __str__(self):
        return 'Unsupported base build %d' % self.baseBuild