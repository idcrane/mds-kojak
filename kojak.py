import json
import urllib2
import csv

import utils # Personal module
import spotipy
import pyen
import pandas as pd
# from pymongo import MongoClient

class TrackAnalysis(object):
    """Class to pull out relevant track information for given band, and analyze it.
    """

    relevant_fields = ['album_album_type', 'album_name', 'album_popularity',
          'album_release_date', 'custom_album_year', 'custom_sp_artist_id', 'en_artist',
          'en_audio_summary_acousticness', 'en_audio_summary_danceability',
          'en_audio_summary_duration', 'en_audio_summary_energy', 'en_audio_summary_instrumentalness',
          'en_audio_summary_key', 'en_audio_summary_liveness', 'en_audio_summary_loudness', 'en_audio_summary_mode',
            'en_audio_summary_speechiness', 'en_audio_summary_tempo', 'en_audio_summary_time_signature',
            'en_audio_summary_valence', 'en_id', 'en_title', 'sp_name', 'sp_uri']

    studio_album_file = 'studioalbums.py'

    def __init__(self, artistname, mongodb, albuminfo=None):
        """ artistname is a string -- oddly enough, the artist's name.
            albuminfo is list of dictionaries, each dictionary must at least include "idnum" key.
            mongodb is pymongo collection object
        """
        self.artistname = artistname
        if albuminfo:
            self.albuminfo = albuminfo
        else:
            self.albuminfo = self._read_album_file(self.studio_album_file, self.artistname)
        self.mongodb = mongodb

    def create_dataframe(self):
        assert self.albuminfo != None
        tracks = []
        # For each album, find all tracks, and then for each track
        # build dictionary using just fields in self.relevant_fields
        album_id_list = [album['albumid'] for album in self.albuminfo]
        for album in album_id_list:
            album_tracks = [{key: track[key] for key in self.relevant_fields} for track in self.mongodb.find({'album_id': album})]
            tracks += album_tracks
        self.df = pd.DataFrame(tracks)

    def _read_album_file(self, filepath, artistname):
        """Read in album file. This assumes a tab seperate file with column
            names 'ALBUMID', 'YEAR', 'BAND', 'ALBUMTITLE'
        """
        artistalbums = []
        with open('studioalbums.tsv', 'r') as infile:
            data = infile.readlines()
            for row in data:
                row = row.replace('\n', '')
                if row[0] == '#':
                    continue
                row = row.split('\t')
                row = [item for item in row if item]
                artistalbums.append({'albumid': row[0], 'year': row[1], 'artist': row[2], 'albumtitle': row[3]})
        singleartistalbums = [album for album in artistalbums if artistname in album['artist']]
        if len(singleartistalbums) == 0:
            print "No albums by %s found in %s" % (artistname, filepath)
        return  singleartistalbums


class MusicGrab(object):
    """Class consisting of functions to get various data from music api services.
       Supported APIs are found in self.services

       To use APIs which require API keys, see self.__init__.__doc__

       Function names begin with the name of the API that they interact with.
    """
    services = ['echonest', 'spotify']
    api_keys = {}
    spotify_limit = 50 # 50 is max number of results to return for Spotify API

    def __init__(self, en_api_key_path=None):
        """Initiates instances of APIs for all services. If a given service
           requires an API key, instance is only initiated if path of file
           with API key as only line is passed when calling the class.
        """
        # Only set api key paths for those services that require API key
        self.spotify = spotipy.Spotify()

        if en_api_key_path != None:
            self.load_api_key('echonest', en_api_key_path)
            self.echonest = pyen.Pyen(self.api_keys['echonest'])

    def load_api_key(self, service, apikeypath):
        """Given service name and path of file containing api key, set the
            api key for that service.

            Service name must be in self.services.
        """
        assert service in self.services
        with open (apikeypath, 'r') as infile:
            self.api_keys[service] = infile.read()

    def echonest_get_spotify_artist_id(self, artistname):
        """ Uses Echonest API to return the Spotify artist id for given artist.
        """
        response = self.echonest.get('song/search', artist=artistname,
                                    results=1, bucket='id:spotify')
        if response['songs'] == []:
            return None
        spotify_artist_id = response['songs'][0]['artist_foreign_ids'][0]['foreign_id'].split(':')[-1]
        return spotify_artist_id

    def spotify_get_artist_albums(self, artistid, album_type='album', **kwargs):
        """ Uses Spotify API to return album ids for given Spotify artist id.
            By default returns those albums that Spotify considers 'albums', as
            opposed to compilations or others.

            Additional keyword arguments passed along to Spotify API call.

            Returns list of album ids, and list of album names.
        """
        album_data = []

        response = self.spotify.artist_albums(artistid, limit=self.spotify_limit, album_type=album_type, **kwargs)
        while len(album_data) < response['total']:
            temp_data = [{'name': album['name'], 'id': album['id']} for album in response['items']]
            album_data += temp_data
            if response['next']:
                response = self.spotify.next(response)

        return album_data

    def spotify_get_album_info(self, albumid):
        """ Uses Spotify API to return album info for given Spotify album id.

            Returns dictionary of album information, as well as a list of
            Spotify track info for the tracks in the album.
        """
        track_info = []

        response = self.spotify.album(albumid)
        response_tracks = response['tracks']
        total_tracks = response_tracks['total']

        while len(track_info) < total_tracks:
            temp_info = [{'uri': track['uri'], 'name': track['name'],
                'disc_num': track['disc_number'], 'track_num': track['track_number'],
                'preview_url': track['preview_url']} for track in response_tracks['items']]
            track_info += temp_info
            if response_tracks['next']:
                response_tracks = self.spotify.next(response_tracks)

        album_info = response
        del album_info['tracks'] # Don't return all track info in album response dictionary
        return album_info, track_info

    def echonest_get_all_song_info(self, songid, track=True):
        """ Uses Echo Nest API to return complete song analysis given song id.

            Song id can either be Echo Nest song id or foreign track id in the
            form 'service:track(song?):id', such as 'spotify:track:id'.

            track=True sets Echo Nest API setting to 'track' instead of 'song'.
            track=True (the default) must be used when using a Spotify id.
        """
        if track:
            s = 'track'
        else:
            s = 'song'
        apistring = s + '/profile'

        # Get audio summary
        response = self.echonest.get(apistring, id=songid, bucket='audio_summary')
        plurals = s + 's'
        track_music_info = utils.flatten(response[s], parent_key='en')

        # Parse url to get detailed audio information
        response = urllib2.urlopen(track_music_info['en_audio_summary_analysis_url'])
        analysis = json.load(response)
        del analysis['meta'] # Useless info
        analysis = utils.flatten(analysis, parent_key='en')
        del analysis['en_track_codestring'] # Useless info
        del analysis['en_track_echoprintstring'] # Useless info
        del analysis['en_track_rhythmstring'] # Useless info
        del analysis['en_track_synchstring'] # Useless info

        # Sanity Check
        # for key in analysis.keys():
        #     if key in track_music_info.keys():
        #         print "ABORTED! track_music_info and analysis share at least one key!"
        #         print "Problem with: ", track_music_info['en_id'], track_music_info['en_title'], key
        #         return track_music_info
        track_music_info.update(analysis)

        return track_music_info

class MusicGrabKojak(MusicGrab):
    """Class to combine MusicGrab functions into workflow for Project Kojak.
       Consists of get... helper functions, and music_grab_by_artist, which
       runs the entire process for a given artist name.
    """
    # def music_grab_by_artist(self, artistname, album_type='album', insert_mongo=False):
    #     """Runs everything aften being given name of artist.

    #        Keyword arg 'album_type' is passed to Spotify api to get all album ids
    #        associated with an aritst. By default album_type='album', so only full
    #        albums by artist are returned (as opposed to compilation). See
    #        Spotify API documentation, or self.spotify_get_artist_albums.__doc__
    #        for more information.

    #        Returns list of dictionaries, one per song.
    #     """
    #     all_artist_songs = []
    #     print "Gathering tracks for %s..." % artistname

            # sp_artist_album_ids = get_all_album_ids(artistname)
    #     for album in enumerate(sp_artist_album_ids):
    #         album_tracks = self.get_all_album_songs(albumid)
    #         print "Found Echo Nest data for %i songs in %s" % (len(album_tracks), album_names[n])

    #         if insert_mongo:
    #             pass #TODO
    #         else:
    #             all_artist_songs += album_tracks

    #     if not insert_mongo:
    #         return all_artist_songs

    def get_all_album_ids(self, artistname, album_type='album', country='US'):
        """Given name of artist, get all album names and Spotify album ids.

            Combines self.echonest_get_spotify_artist_id and
            self.spotify_get_artist_albums
        """
        sp_artist_id = self.echonest_get_spotify_artist_id(artistname)
        if sp_artist_id == None:
            return None
        sp_artist_album_ids = self.spotify_get_artist_albums(sp_artist_id,
                                            album_type=album_type, country=country)
        print "Number of albums found: %i" % len(sp_artist_album_ids)
        return sp_artist_album_ids


    def get_all_album_songs(self, albumid, insert_mongo=False, mongo_collection=None):
        """Given Spotify album id, get information for all songs.

            For each track, combines Spotify album data, Spotify track
            data, and Echonest track data.

            Will skip over those tracks for which Echo Nest has no information.

            If insert_mongo=False (default),
            returns list of dictionaries, one per track in album.

            If insert_mongo=True, inserts each track into mongo_collection.
        """
        if insert_mongo:
            assert mongo_collection != None

        album_tracks = []
        tracks_inserted = 0
        sp_album_info, sp_track_info = self.spotify_get_album_info(albumid)
        sp_album_data = utils.flatten(sp_album_info, parent_key='album')

        for track in sp_track_info:
            try:
                full_track_data = self.echonest_get_all_song_info(track['uri'])
            except:
                continue

            sp_track_data = utils.flatten(track, parent_key='sp')
            full_track_data.update(sp_track_data)
            full_track_data.update(sp_album_data)

            if insert_mongo:
                self.insert_song_mongo(full_track_data, mongo_collection)
                tracks_inserted += 1
            else:
                album_tracks.append(full_track_data)

        if insert_mongo:
            print "Number of songs inserted into Mongo: %i" % tracks_inserted
        else:
            return album_tracks

    def insert_song_mongo(self, track, mongo_collection):
        """ Given track dictionary and mongodb object, insert song into
            that mongo collection.
        """
        mongo_collection.insert(track)
