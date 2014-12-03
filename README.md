###Trends in the Music of Long-Lived Bands

*This is a work in progress*

This project focuses on pulling together information from The Echo Nest API and Spotify to visualize trends in the music of bands. The Echo Nest provides song parameters (tempo, key, danceability, etc), while Spotify provides album level data (such as release year), as well as the current popularity on Spotify. 

Currently analysis is done in the IPython notebook, where you can select an audio parameter, and be directed to an interactive Plot.ly graph to play with the data, see metadata for that song, or get a 30 second preview of the song from Spotify. The .py file provides classes and methods for the notebook. 

The presentation shows some findings (i.e. the most popular music today of bands that started in the late 60s comes from their first decade, while the most popular music today of bands that started in the early 80s is much more varied). 

Data is stored in MongoDB, and can be gathered using the MusicGrabKojak class in kojak.py

####To Do:
- Move visualization over to d3
- Develop web app to grab band information, and allow easier selection of audio data to display
