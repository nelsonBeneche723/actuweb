import datetime
import time
from pyradios import RadioBrowser
from flask import (Flask, render_template, request, redirect, url_for, jsonify, Response,
                   session, flash, send_from_directory)
import os
import requests
from dotenv import load_dotenv  # Pour lire les fichiers de type (. env)
import google.generativeai as genai  # Pour l'utilisation de l'IA Gemini
import random
from deep_translator import GoogleTranslator  # Pour traduction de données météos
from collections import defaultdict
from datetime import datetime, timedelta
import pytz  # converti l'heure selon la timezone défini
import feedparser  # pour utiliser des flux rss pour les donnees sur le web
import sqlite3
import io
import base64
# import numpy as np
import matplotlib.pyplot as plt
# import matplotlib
import lyricsgenius
from googleapiclient.discovery import build # pour les videos youtube
from babel.dates import format_date, format_datetime
from flask_mail import Mail, Message
import hashlib
import mailtrap as mt
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
import bleach

# chargement du fichier .env
load_dotenv()
#instanciation de la Flask
app = Flask(__name__)
# Générer un clé secret
app.secret_key = "je_suis_sony_devweb+"
csrf = CSRFProtect()
csrf.init_app(app)

app.config['BABEL_DEFAULT_TIMEZONE']='America/Port-au-Prince'
lien_database = 'musique_bunny.db'

def envoyer_email(email):
    msg = Message('Notification', recipients=[email])
    msg.body = ("Cher nouvel utilisateur,Nous vous remercions d'avoir créé un compte sur notre site web actuwebmedia.\n"
                "\nNous sommes ravis de vous accueillir au sein de notre communauté de passionnés de musique. "
                "\nVous pouvez désormais laisser vos commentaires et avis sur les différentes musiques présentes sur notre plateforme."
                "\nN'hésitez pas à nous faire part de vos impressions et de vos coups de cœur. Votre feedback nous est précieux pour enrichir notre catalogue musical."
                "\nSi vous avez la moindre question, n'hésitez pas à nous contacter. Nous restons à votre écoute."
                "\n\nCordialement, L'équipe actuwebmedia")
    # mail.send(msg)
    return 'Email envoyé'

def jouer_musique_aprescommentaires(musique_id, titre):
    conn = sqlite3.connect(lien_database)
    conn.row_factory = sqlite3.Row  # accès par nom de colonne
    cur = conn.cursor()
    # Recherche du titre avec slug transformé
    titre_recherche = titre.replace('-', ' ')
    cur.execute("SELECT * FROM musiques WHERE id=? AND titre LIKE ?", (musique_id, titre_recherche))
    musique = cur.fetchone()
    if not musique:
        return '<p style="text-align:center;">Musique introuvable ou erreur du serveur..</p>', 404
    resultatmusique = {
        'id': musique['id'],
        'nom': musique['nom'],
        'url': musique['url'],
        'titre': musique['titre'],
        'image_url': musique['image_url'],
        'taille': musique['taille'],
        'date_modification': musique['date_modification'],
        'genre': musique['genre']
    }
    # Recommandations par artiste ou genre
    id = musique['id']
    genre = musique['genre']
    req = cur.execute('Select * from musiques where id !=? and genre=? order by random() limit 12', (id, genre))
    recommandations = req.fetchall()
    # Plus de contenu selon le style de musique (Rap)
    plus_contenu_musique = afficherpluscontenu(id, genre)
    conn.close()
    # récupérer les paroles pour cette chanson
    # Valeur par défaut
    paroles = "Paroles pas encore disponibles"

    try:
        genius = lyricsgenius.Genius(os.getenv('api_key_genius'), timeout=10)
        #
        result = genius.search_song(musique['titre'], musique['nom'])
        if result:
            paroles = result.lyrics
        else:
            paroles = "Paroles pas encore disponibles"
    except Exception as e:
        print(f"Erreur de connexion : {e}")
        paroles = "Problème de connexion. Veuillez réessayer."

    return resultatmusique,  recommandations, plus_contenu_musique, paroles

def aff_stationradio():
    # Dictionnaire avec des flux de radio et des images
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select * from stationradios limit 30")
    connection.commit()
    stations = []
    for result in req.fetchall():
        stations.append({'nom': result[1],'url': result[2], 'images': result[3]})
    # stations = []  # initialiser une variable vide pour stocker tous les messages
    # on va faire un choix aleatoire pour affichage les stations par nombre de 12.
    # choix_a = dict(random.sample(list(mydictstream.items()), 12))
    # Boucle pour itérer sur les éléments du dictionnaire
    # renvoyer un message à l'utilisateur
    return stations

def classementchampionnat_france():
    competition_id = 'FL1'  # Ex: Ligue 1
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/standings'

    headers = {
        'X-Auth-Token': os.getenv('api_key_sports')
    }
    response = requests.get(url, headers=headers)  # reponse de l'api apres la requete https
    classementfrance = []
    nomequipes = []
    nbpoints = []
    image_base64 = None
    colors = []
    # si l'api renvoi des valeurs
    if response.status_code == 200:
        data = response.json()
        table = data['standings'][0]['table']
        for i, team in enumerate(table):
            classementfrance.append({'position':team['position'],'equipe': team['team']['name'], 'journee':team['playedGames'],'points': team['points'],
                                     'gagne':team['won'],'nul':team['draw'],'perdu':team['lost'],'buts_marques':team['goalsFor'],'buts_encaisses':team['goalsAgainst'],'difference':team['goalDifference']})
            nomequipes.append(team['team']['name'])
            nbpoints.append(team['points'])
            # Colorier en rouge les 3 derniers (relégués), sinon bleu
            if i < 2:
                colors.append('mediumseagreen')  # Europe
            elif i >= len(table) - 3:
                colors.append('crimson')  # relegation
            else:
                colors.append('skyblue')  # milieu tableau
        # Générer le graphique
        fig, ax = plt.subplots(figsize=(13, 6))
        ax.barh(nomequipes[::-1], nbpoints[::-1], color=colors[::-1], height=0.6)  # Inversé pour que le 1er soit en haut
        ax.set_title("Classement du Championnat")
        ax.set_ylabel("Points")
        plt.tight_layout()
        # sauvegarde en memoire
        buf = io.BytesIO()
        # enregistrer sous le format png
        plt.savefig(buf, format='png', bbox_inches="tight")
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return classementfrance, image_base64
    else:
        print(f"Erreur : {response.status_code}")

def calendrier_ligue1():
    API_KEY = os.getenv('api_key_sports')
    competition_id = 'FL1'  # Ligue 1
    time_zone = pytz.timezone('America/Port-au-Prince')
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches'
    headers = {'X-Auth-Token': API_KEY}
    match_ligue1_auj = []
    match_ligue1_dem = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matchs = data.get('matches', [])
        today = datetime.now(time_zone).date()
        tomorrow = today + timedelta(days=1)
        for match in matchs:
            utc_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            # Passer en timezone locale
            local_time = utc_time.astimezone(time_zone)
            match_date = local_time.date()
            if match_date == today:
                match_ligue1_auj.append({
                    'domicile': match['homeTeam']['name'],
                    'exterieur': match['awayTeam']['name'],
                    'date': local_time.strftime('%d/%m/%Y %H:%M')
                })
            elif match_date == tomorrow:
                match_ligue1_dem.append({
                    'domicile_dem': match['homeTeam']['name'],
                    'exterieur_dem': match['awayTeam']['name'],
                    'date_dem': local_time.strftime('%d/%m/%Y %H:%M')
                })

        return match_ligue1_auj, match_ligue1_dem
    else:
        print(f"Erreur API : {response.status_code}")
        return [], []

def classementchampionnat_espagne():
    competition_id = 'PD'  # Ex: Ligue 1
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/standings'
    headers = {
        'X-Auth-Token': os.getenv('api_key_sports')
    }
    response = requests.get(url, headers=headers)  # on effectue une requete vers l'api
    classementespagne = []
    nomsequipes = []
    points = []
    colors = []
    image_base64 = None
    # si l'api renvoi des valeurs
    if response.status_code == 200:
        data = response.json()  # on transforme la reponse en format json
        table = data['standings'][0]['table']
        # parcourir l'ensemble de valeurs de la table
        for i, team in enumerate(table):
            classementespagne.append({'position':team['position'],'equipe': team['team']['name'],'journee':team['playedGames'], 'points': team['points'],
                                     'gagne':team['won'],'nul':team['draw'],'perdu':team['lost'],'buts_marques':team['goalsFor'],'buts_encaisses':team['goalsAgainst'],'difference':team['goalDifference']})
            nomsequipes.append(team['team']['name'])
            points.append(team['points'])
            if i < 3:
                colors.append('mediumseagreen')
            elif i >=len(table) -3:
                colors.append('crimson')
            else:
                colors.append('skyblue')
        # maintenant on cree le graphe (barh)
        fig, ax = plt.subplots(figsize=(13, 6))
        ax.set_title('Classement du championnat Espagne')
        ax.set_ylabel('Points')
        ax.barh(nomsequipes[::-1], points[::-1], color=colors[::-1], height=0.6)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')

        return classementespagne, image_base64
    else:
        print(f"Erreur : {response.status_code}")

def calendrier_espagne():
    API_KEY = os.getenv('api_key_sports')
    competition_id = 'PD'  # Ligue 1
    time_zone = pytz.timezone('America/Port-au-Prince')
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches'
    headers = {'X-Auth-Token': API_KEY}
    match_esp_auj = []
    match_esp_dem = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matchs = data.get('matches', [])
        today = datetime.now(time_zone).date()
        tomorrow = today + timedelta(days=1)
        for match in matchs:
            utc_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            # Passer en timezone locale
            local_time = utc_time.astimezone(time_zone)
            match_date = local_time.date()
            if match_date == today:
                match_esp_auj.append({
                    'domicile': match['homeTeam']['name'],
                    'exterieur': match['awayTeam']['name'],
                    'date': local_time.strftime('%d/%m/%Y %H:%M')
                })
            elif match_date == tomorrow:
                match_esp_dem.append({
                    'domicile_dem': match['homeTeam']['name'],
                    'exterieur_dem': match['awayTeam']['name'],
                    'date_dem': local_time.strftime('%d/%m/%Y %H:%M')
                })

        return match_esp_auj, match_esp_dem
    else:
        print(f"Erreur API : {response.status_code}")
        return [], []

def classementchampionnat_angleterre():
    competition_id = 'PL'  # Ex: Ligue 1
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/standings'
    headers = {
        'X-Auth-Token': os.getenv('api_key_sports')
    }
    response = requests.get(url, headers=headers)  # Reponse de l'api apres la requete https
    classementangleterre = []
    nomsequipes = []
    points = []
    colors = []
    # si l'api renvoi des valeurs
    if response.status_code == 200:
        data = response.json()
        table = data['standings'][0]['table']
        for i, team in enumerate(table):
            classementangleterre.append({'position':team['position'],'equipe': team['team']['name'],'journee':team['playedGames'], 'points': team['points'],
                                     'gagne':team['won'],'nul':team['draw'],'perdu':team['lost'],'buts_marques':team['goalsFor'],'buts_encaisses':team['goalsAgainst'],'difference':team['goalDifference']})
            nomsequipes.append(team['team']['name'])
            points.append(team['points'])
            if i < 3:
                colors.append('mediumseagreen')
            elif i >=len(table) -3:
                colors.append('crimson')
            else:
                colors.append('skyblue')
        # maintenant on cree le graphe (barh)
        fig, ax = plt.subplots(figsize=(13, 6))
        ax.set_title('Classement du championnat Espagne')
        ax.set_ylabel('Points')
        ax.barh(nomsequipes[::-1], points[::-1], color=colors[::-1], height=0.6)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return classementangleterre, image_base64
    else:
        print(f"Erreur : {response.status_code}")

def calendrier_angleterre():
    API_KEY = os.getenv('api_key_sports')
    competition_id = 'PL'  # Ligue 1
    time_zone = pytz.timezone('America/Port-au-Prince')
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches'
    headers = {'X-Auth-Token': API_KEY}
    match_ang_auj = []
    match_ang_dem = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matchs = data.get('matches', [])
        today = datetime.now(time_zone).date()
        tomorrow = today + timedelta(days=1)
        for match in matchs:
            utc_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            # Passer en timezone locale
            local_time = utc_time.astimezone(time_zone)
            match_date = local_time.date()
            if match_date == today:
                match_ang_auj.append({
                    'domicile': match['homeTeam']['name'],
                    'exterieur': match['awayTeam']['name'],
                    'date': local_time.strftime('%d/%m/%Y %H:%M')
                })
            elif match_date == tomorrow:
                match_ang_dem.append({
                    'domicile_dem': match['homeTeam']['name'],
                    'exterieur_dem': match['awayTeam']['name'],
                    'date_dem': local_time.strftime('%d/%m/%Y %H:%M')
                })

        return match_ang_auj, match_ang_dem
    else:
        print(f"Erreur API : {response.status_code}")
        return [], []

def classementchampionnat_italie():
    competition_id = 'SA'  # Ex: Ligue 1
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/standings'
    headers = {
        'X-Auth-Token': os.getenv('api_key_sports')
    }
    response = requests.get(url, headers=headers)  # Reponse de l'api apres la requete https
    classementitalie = []
    nomsequipes = []
    points = []
    colors = []
    # si l'api renvoi des valeurs
    if response.status_code == 200:
        data = response.json()
        table = data['standings'][0]['table']
        for i, team in enumerate(table) :
            classementitalie.append({'position':team['position'],'equipe': team['team']['name'],'journee':team['playedGames'], 'points': team['points'],
                                     'gagne':team['won'],'nul':team['draw'],'perdu':team['lost'],'buts_marques':team['goalsFor'],'buts_encaisses':team['goalsAgainst'],'difference':team['goalDifference']})
            nomsequipes.append(team['team']['name'])
            points.append(team['points'])
            if i < 3:
                colors.append('mediumseagreen')
            elif i >=len(table) -3:
                colors.append('crimson')
            else:
                colors.append('skyblue')
        # maintenant on cree le graphe (barh)
        fig, ax = plt.subplots(figsize=(13, 6))
        ax.set_title('Classement du championnat Espagne')
        ax.set_ylabel('Points')
        ax.barh(nomsequipes[::-1], points[::-1], color=colors[::-1], height=0.6)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return classementitalie, image_base64
    else:
        print(f"Erreur : {response.status_code}")

def calendrier_italie():
    API_KEY = os.getenv('api_key_sports')
    competition_id = 'SA'  # Ligue 1
    time_zone = pytz.timezone('America/Port-au-Prince')
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches'
    headers = {'X-Auth-Token': API_KEY}
    match_ita_auj = []
    match_ita_dem = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matchs = data.get('matches', [])
        today = datetime.now(time_zone).date()
        tomorrow = today + timedelta(days=1)
        for match in matchs:
            utc_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            # Passer en timezone locale
            local_time = utc_time.astimezone(time_zone)
            match_date = local_time.date()
            if match_date == today:
                match_ita_auj.append({
                    'domicile': match['homeTeam']['name'],
                    'exterieur': match['awayTeam']['name'],
                    'date': local_time.strftime('%d/%m/%Y %H:%M')
                })
            elif match_date == tomorrow:
                match_ita_dem.append({
                    'domicile_dem': match['homeTeam']['name'],
                    'exterieur_dem': match['awayTeam']['name'],
                    'date_dem': local_time.strftime('%d/%m/%Y %H:%M')
                })

        return match_ita_auj, match_ita_dem
    else:
        print(f"Erreur API : {response.status_code}")
        return [], []

def classementchampionnat_allemagne():
    competition_id = 'BL1'  # Ex: Ligue 1
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/standings'
    headers = {
        'X-Auth-Token': os.getenv('api_key_sports')
    }
    response = requests.get(url, headers=headers)  # Reponse de l'api apres la requete https
    classementallemagne = []
    colors = []
    nomsequipes = []
    points = []
    # si l'api renvoi des valeurs
    if response.status_code == 200:
        data = response.json()
        table = data['standings'][0]['table']
        for i, team in enumerate(table):
            classementallemagne.append({'position':team['position'],'equipe': team['team']['name'],'journee':team['playedGames'], 'points': team['points'],
                                     'gagne':team['won'],'nul':team['draw'],'perdu':team['lost'],'buts_marques':team['goalsFor'],'buts_encaisses':team['goalsAgainst'],'difference':team['goalDifference']})
            nomsequipes.append(team['team']['name'])
            points.append(team['points'])
            if i < 3:
                colors.append('mediumseagreen')
            elif i >=len(table) -3:
                colors.append('crimson')
            else:
                colors.append('skyblue')
        # maintenant on cree le graphe (barh)
        fig, ax = plt.subplots(figsize=(13, 6))
        ax.set_title('Classement du championnat Espagne')
        ax.set_ylabel('Points')
        ax.barh(nomsequipes[::-1], points[::-1], color=colors[::-1], height=0.6)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return classementallemagne, image_base64
    else:
        print(f"Erreur : {response.status_code}")

def calendrier_allemagne():
    API_KEY = os.getenv('api_key_sports')
    competition_id = 'BL1'  # Ligue 1
    time_zone = pytz.timezone('America/Port-au-Prince')
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches'
    headers = {'X-Auth-Token': API_KEY}
    match_all_auj = []
    match_all_dem = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        matchs = data.get('matches', [])
        today = datetime.now(time_zone).date()
        tomorrow = today + timedelta(days=1)
        for match in matchs:
            utc_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            # Passer en timezone locale
            local_time = utc_time.astimezone(time_zone)
            match_date = local_time.date()
            if match_date == today:
                match_all_auj.append({
                    'domicile': match['homeTeam']['name'],
                    'exterieur': match['awayTeam']['name'],
                    'date': local_time.strftime('%d/%m/%Y %H:%M')
                })
            elif match_date == tomorrow:
                match_all_dem.append({
                    'domicile_dem': match['homeTeam']['name'],
                    'exterieur_dem': match['awayTeam']['name'],
                    'date_dem': local_time.strftime('%d/%m/%Y %H:%M')
                })

        return match_all_auj, match_all_dem
    else:
        print(f"Erreur API : {response.status_code}")
        return [], []

def infos_sports():
    sportsactu = []
    connection = True
    url_rss = 'https://www.lemonde.fr/sport/rss_full.xml'
    feed = feedparser.parse(url_rss)
    sports = feed.entries
    # Retrouver des infos sur le site www.lemonde.fr par a son flux RSS
    try:
        for sport in sports:
            image_url = None
            # Cherche une image dans 'media_content'
            if 'media_content' in sport:
                for media in sport['media_content']:
                    if 'url' in media:
                        image_url = media['url']
                        break  # Prend la première image
            # Ou dans les 'links' avec type image
            elif 'links' in sport:
                for link in sport['links']:
                    if link.get('type', '').startswith('image'):
                        image_url = link.get('href')
                        break

        # Création du dictionnaire de l'article
            sportsactu.append({'title': sport.get('title'), 'link': sport.get('link'), 'summary': sport.get('summary'),'published': sport.get('published'), 'image': image_url})
        return sportsactu  # retourner la valeur de la fonction
    except Exception as e:
        print(f'Erreur API Sports...{e}')

def affichermusique_genre(genre):
    resultcompas = []
    connection = sqlite3.connect(lien_database)
    cursor = connection.cursor()
    cursor.execute("select * from musiques where lower(trim(genre))=? order by random() limit 20", (genre, ))
    connection.commit()
    for row in cursor.fetchall():
        resultcompas.append({'id': row[0],'titre': row[5], 'auteur': row[5],'musique':row[4], 'image': row[6]})
    print("d'accord: musiques compas")
    return resultcompas

def affichermusique_afrobeat():
    genre = 'afrobeat'
    resultafro = []
    connection = sqlite3.connect(lien_database)
    cursor = connection.cursor()
    req = cursor.execute("select * from musiques where lower(TRIM(genre))=? order by random() limit 20", (genre,))
    connection.commit()
    for row in req.fetchall():
        resultafro.append({'id': row[0],'titre': row[5], 'auteur': row[5],'musique':row[4], 'image': row[6]})
    print("Affichage: Musiques Afrobeat")
    return resultafro

def affichermusique_evangelique():
    genre = 'evangelique'
    resultafro = []
    connection = sqlite3.connect(lien_database)
    cursor = connection.cursor()
    req = cursor.execute("select * from musiques where lower(TRIM(genre))=? order by random() limit 20", (genre,))
    connection.commit()
    for row in req.fetchall():
        resultafro.append({'id': row[0],'titre': row[5], 'auteur': row[5],'musique':row[4], 'image': row[6]})
    print("d'accord: musiques evangeliques..")
    return resultafro

def affichermusique_rap():
    genre = 'rap'
    resultrap = []
    connection = sqlite3.connect(lien_database)
    cursor = connection.cursor()
    req = cursor.execute("select * from musiques where lower(TRIM(genre))=? order by random() limit 20", (genre,))
    connection.commit()
    for row in req.fetchall():
        resultrap.append({'id': row[0],'titre': row[5], 'auteur': row[5],'musique':row[4], 'image': row[6]})
    print("d'accord: musiques afrobeat")
    return resultrap

def afficherpluscontenu(id, genre):
    # genre = ['compas', 'rap', 'evangelique','afrobeat', 'gospel']
    # genre_aleatoire = random.choice(genre)
    resultrap = []
    connection = sqlite3.connect(lien_database)
    cursor = connection.cursor()
    req = cursor.execute("select * from musiques where id !=? and genre !=? order by random() limit 8", (id, genre))
    connection.commit()
    for row in req.fetchall():
        # convertir la durée en format Minutes:Secondes
        # secondes = int(row[4])
        # temps = str(timedelta(seconds=secondes))
        resultrap.append({'id': row[0],'titre': row[5], 'auteur': row[5],'musique':row[4], 'image': row[6], 'genre': row[7]})
    print("Affichage: Musiques Afrobeat...")
    return resultrap

def recuperer_info_utilisateur():
    # ip = request.headers.get('X-Forwarded-For', request.remote_addr) # On récupère de l'adresse ip de hote
    # utilisation d'une autre methode de recuperation des donnees des visiteurs
    # ip = request.remote_addr
    ip = request.remote_addr
    user = request.remote_user
    # url = f"https://api.ipapi.com/{ip}?access_key={user}&hostname=1"
    url = f"https://ipinfo.io/{ip}/json"
    response = requests.get(url)  # on effectue une requete https afin de recuperer le pays hote
    data = response.json()  # transformer le resultat dans format json
    print(data)
    pays = data.get('country','inconnu')

    # connection = sqlite3.connect('locationutilisateur.db')
    # cursor = connection.cursor()
    # cursor.execute('create table if not exists location(id integer primary key autoincrement,adresse_ip TEXT, pays TEXT)')
    # cursor.execute('insert into location(adresse_ip,pays) values(?,?)', (ip, pays))
    # connection.commit()
    # print("votre adresse ip: ,"+ip+","+data.get('country','inconnu')+"")?

def calendriermatch():
    API_KEY = os.getenv('api_key_sports')
    url = 'https://api.football-data.org/v4/matches'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    resultat = []
    try:
        if response.status_code == 200:
            data = response.json()
            matches = data.get('matches', [])
            if matches:
                # Regrouper par date, puis par compétition
                grouped_matches = defaultdict(lambda: defaultdict(list))
                # parcourir les matches
                for match in matches:
                    # Convertir date UTC en heure Port au Prince et extraire la date et l'heure
                    dt_utc = match['utcDate'] # format date: 2021-09-09T19:01:00Z
                    date_formate = datetime.strptime(dt_utc, '%Y-%m-%dT%H:%M:%SZ')
                    py_tz = pytz.timezone('America/Port-au-Prince')
                    localdate = date_formate.astimezone(py_tz)
                    date = localdate.date()
                    # convertir par exemple august=aout
                    date_f = format_date(date, format='d MMMM y', locale='fr')
                    time_str = localdate.time().strftime('%H:%M')
                    # competitions (nom competition, domicile, a l'extérieur)
                    competition = match['competition']['name']
                    home = match['homeTeam']['name']
                    away = match['awayTeam']['name']
                    grouped_matches[date_f][competition].append(f"{time_str} — {home} vs {away}")
                    # ✅ Affichage
                for date_f, comps in grouped_matches.items():
                    for comp, matchs in comps.items():
                        for m in matchs:
                            resultat.append({"date": f"{date_f}", 'competition': comp, 'match': m})
                return resultat
            else:
                print("Aucun match disponible.")
    except Exception as e:
        return None, str(e)

def matchsencours_premierleague():
    API_KEY = '0dceee736fbb4e52a8fb909175f99d07'  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/PL/matches?status=IN_PLAY'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    resultat_mpl = []
    data = response.json()
    # verifier l'api renvoie une response(ok)
    try:
        if response.status_code == 200:
            for match in data.get('matches', []):
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                # scores equipe dehors, equipe domicile
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # date
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                date_ = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = date_.astimezone(py_tz)
                localdate = localdate - timedelta(hours=4)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure_utc = localdate.time().strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, e`tc.
                competition = match['competition']['name']
                minutes = match['score']['duration']
                # ajouter les resultats dans une liste contenant un dictionnaire
                resultat_mpl.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': f"{date_f}/{heure_utc}",
                    'competition': competition,
                    'minutes': minutes
                })
            return resultat_mpl
    except Exception as e:
        return None, str(e)

def matchsencours_liga():
    API_KEY = os.getenv('api_key_sports')  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/PD/matches?status=IN_PLAY'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    resultat_mpd = []
    # verifier l'api renvoie une response(ok)
    try:
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                # scores equipe dehors, equipe domicile
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # date
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                date_ = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = date_.astimezone(py_tz)
                localdate = localdate - timedelta(hours=4)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure_utc = localdate.time().strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, e`tc.
                competition = match['competition']['name']
                minutes = match['score']['duration']
                # ajouter les resultats dans une liste contenant un dictionnaire
                resultat_mpd.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': f'{date_f}/{heure_utc}',
                    'competition': competition,
                    'minutes': minutes
                })
            return resultat_mpd
    except Exception as e:
        return None, str(e)

def matchsencours_seriea():
    API_KEY = os.getenv('api_key_sports')  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/SA/matches?status=IN_PLAY'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    resultat_msa = []
    try:
        # verifier l'api renvoie une response(ok)
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                # scores equipe dehors, equipe domicile
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # date
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                date_ = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = date_.astimezone(py_tz)
                localdate = localdate - timedelta(hours=4)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure_utc = localdate.time().strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, e`tc.
                competition = match['competition']['name']
                minutes = match['score']['duration']
                # ajouter les resultats dans une liste contenant un dictionnaire
                resultat_msa.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': f'{date_f}/{heure_utc}',
                    'competition': competition,
                    'minutes': minutes
                })
            return resultat_msa
    except Exception as e:
        return None, str(e)

def matchsencours_bundesliga():
    API_KEY = os.getenv('api_key_sports') # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/BL1/matches?status=IN_PLAY'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    resultat_mbl1 = []
    # verifier l'api renvoie une response(ok)
    try:
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                # scores equipe dehors, equipe domicile
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # date
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                date_ = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = date_.astimezone(py_tz)
                localdate = localdate - timedelta(hours=4)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure_utc = localdate.time().strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, e`tc.
                competition = match['competition']['name']
                minutes = match['score']['duration']
                # ajouter les resultats dans une liste contenant un dictionnaire
                resultat_mbl1.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': f'{date_f}/{heure_utc}',
                    'competition': competition,
                    'minutes': minutes
                })
            return resultat_mbl1
    except Exception as e:
        return None, str(e)

def matchsencours_ligue1():
    API_KEY = os.getenv('api_key_sports')  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/FL1/matches?status=IN_PLAY'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    resultat_mfl1 = []
    # verifier l'api renvoie une response(ok)
    try:
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                # scores équipe dehors, équipe domicile
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # date
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                date_ = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = date_.astimezone(py_tz)
                localdate = localdate - timedelta(hours=4)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure_utc = localdate.time().strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, e`tc.
                competition = match['competition']['name']
                minutes = match['score']['duration']
                # ajouter les résultats dans une liste contenant un dictionnaire
                resultat_mfl1.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': f'{date_f}/{heure_utc}',
                    'competition': competition,
                    'minutes': minutes
                })
            return resultat_mfl1

    except Exception as e:
        return None, str(e)

def matchtermine_pl():
    API_KEY = os.getenv('api_key_sports') # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    try:
        if response.status_code == 200:
            resultat_tpl = []
            derniers = sorted(data['matches'], key=lambda x:x['utcDate'], reverse=True)[:10]
            for match in derniers:
                home_team = match['homeTeam']['name']
                away_team = match['awayTeam']['name']
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                # converti les dates
                utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
                utc_date = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                py_tz = pytz.timezone('America/Port-au-Prince')
                localdate = utc_date.astimezone(py_tz)
                date = localdate.date()
                # convertir par exemple august=aout
                date_f = format_date(date, format='d MMMM y', locale='fr')
                heure = localdate.strftime('%H:%M')
                status = match['status']  # SCHEDULED, FINISHED, etc.
                competition = match['competition']['name']
                # dictionnaire de donnees
                resultat_tpl.append({
                    'home': home_team,
                    'away': away_team,
                    'score': f"{score_home} - {score_away}",
                    'status': status,
                    'date': date_f,
                    'heure': heure,
                    'competition': competition
                })
            return resultat_tpl
        else:
            print('echec')

    except Exception as e:
        print("Erreur :")

def matchtermine_liga():
    API_KEY = os.getenv('api_key_sports') # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/PD/matches?status=FINISHED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    resultat_tlig = []
    derniers = sorted(data['matches'], key=lambda x: x['utcDate'], reverse=True)[:10]
    if response.status_code == 200:
        for match in derniers:
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            score_home = match['score']['fullTime']['home']
            score_away = match['score']['fullTime']['away']
            utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
            # converti les dates
            utc_date = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
            py_tz = pytz.timezone('America/Port-au-Prince')
            localdate = utc_date.astimezone(py_tz)
            date = localdate.date()
            # convertir par exemple august=aout
            date_f = format_date(date, format='d MMMM y', locale='fr')
            heure = localdate.strftime('%H:%M')

            status = match['status']  # SCHEDULED, FINISHED, etc.
            competition = match['competition']['name']

            resultat_tlig.append({
                'home': home_team,
                'away': away_team,
                'score': f"{score_home} - {score_away}",
                'status': status,
                'date': date_f,
                'heure': heure,
                'competition': competition
            })
        return resultat_tlig
    else:
        print("Erreur :")

def matchtermine_seriea():
    API_KEY = os.getenv('api_key_sports') # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/SA/matches?status=FINISHED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    resultat_tsa = []

    if response.status_code == 200:
        data = response.json()
        derniers = sorted(data['matches'], key=lambda x: x['utcDate'], reverse=True)[:10]
        for match in derniers:
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            score_home = match['score']['fullTime']['home']
            score_away = match['score']['fullTime']['away']
            utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z

            utc_date = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
            py_tz = pytz.timezone('America/Port-au-Prince')
            localdate = utc_date.astimezone(py_tz)
            date = localdate.date()
            # convertir par exemple august=aout
            date_f = format_date(date, format='d MMMM y', locale='fr')

            heure = localdate.strftime('%H:%M')
            status = match['status']  # SCHEDULED, FINISHED, etc.
            competition = match['competition']['name']

            resultat_tsa.append({
                'home': home_team,
                'away': away_team,
                'score': f"{score_home} - {score_away}",
                'status': status,
                'date': date_f,
                'heure': heure,
                'competition': competition
            })
        return resultat_tsa
    else:
        print("Erreur :")

def matchtermine_ligue1():
    API_KEY = os.getenv('api_key_sports')  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/FL1/matches?status=FINISHED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    resultat_tlig1 = []

    if response.status_code == 200:
        data = response.json()
        derniers = sorted(data['matches'], key=lambda x: x['utcDate'], reverse=True)[:10]
        for match in derniers:
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']

            score_home = match['score']['fullTime']['home']
            score_away = match['score']['fullTime']['away']

            utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
            utc_date = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
            py_tz = pytz.timezone('America/Port-au-Prince')
            localdate = utc_date.astimezone(py_tz)
            date = localdate.date()
            # convertir par exemple august=aout
            date_f = format_date(date, format='d MMMM y', locale='fr')
            heure = localdate.strftime('%H:%M')
            status = match['status']  # SCHEDULED, FINISHED, etc.
            competition = match['competition']['name']

            resultat_tlig1.append({
                'home': home_team,
                'away': away_team,
                'score': f"{score_home} - {score_away}",
                'status': status,
                'date': date_f,
                'heure': heure,
                'competition': competition
            })
        return resultat_tlig1
    else:
        print("Erreur :")

def recupererscorejoueur(championnat):
    API_KEY = os.getenv('api_key_sports')
    headers = {'X-Auth-Token': API_KEY}
    url = f'https://api.football-data.org/v4/competitions/{championnat}/scorers'
    response = requests.get(url, headers=headers)
    resultat = []
    try:
        if response.status_code == 200:
            data = response.json()
            for scorer in data['scorers']:
                player_name = scorer['player']['name']
                team_name = scorer['team']['name']
                goals = scorer['goals']
                # dictionnaire de donnees du resultat
                resultat.append({
                    'player_name': player_name,
                    'team_name': team_name,
                    'goals': goals
                })
            return resultat
        else:
            print('Erreur de reponse')
    except Exception as e:
        print(f"Erreur API{e}")

def scorer_europeen():
    topscorerpl = recupererscorejoueur('PL')
    topscorerpd = recupererscorejoueur('PD')
    topscorersa = recupererscorejoueur('SA')
    topscorerfl1 = recupererscorejoueur('FL1')
    topscorerbl1 = recupererscorejoueur('BL1')

    topsc = []
    result1 = next(((maxscorepl['player_name'], maxscorepl['goals']) for maxscorepl in topscorerpl if maxscorepl['goals'] > 0), None)
    result2 = next(((maxscorepd['player_name'], maxscorepd['goals']) for maxscorepd in topscorerpd if maxscorepd['goals'] > 0), None)
    result3 = next(((maxscoresa['player_name'], maxscoresa['goals']) for maxscoresa in topscorersa if maxscoresa['goals'] > 0), None)
    result4 = next(((maxscorefl1['player_name'], maxscorefl1['goals']) for maxscorefl1 in topscorerfl1 if maxscorefl1['goals'] > 0), None)
    result5 = next(((maxscorebl1['player_name'], maxscorebl1['goals']) for maxscorebl1 in topscorerbl1 if maxscorebl1['goals'] > 0), None)

    topsc.append({'Angleterre': result1, 'Espagne': result2, 'Italie': result3, 'France': result4, 'Allemagne': result5})
    # print(f"'Angletere':result1 , 'Espagne':{result2}, 'Italie':{result3}, 'France': {result4}, 'Allemagne': {result5}")

    # parcourir la liste de dictionnaire
    max_buts = 0
    meilleur_joueur = []

    for d in topsc:
        for pays, (joueur, buts) in d.items():

            if buts > max_buts:
                max_buts = buts
                # meilleur_joueur = joueur
                pays_meilleur = pays
                print(pays_meilleur, joueur, max_buts)
                meilleur_joueur = [{"pays":pays,
                                    "joueur":joueur,
                                    "buts":buts
                                    }]
            elif buts == max_buts:
                meilleur_joueur.append({"pays":pays,"joueur":joueur, "buts":buts})
        return meilleur_joueur

def matchtermine_bundesliga():
    API_KEY = os.getenv('api_key_sports')  # Remplace par ta vraie clé API
    url = 'https://api.football-data.org/v4/competitions/BL1/matches?status=FINISHED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    resultat_tligb = []
    if response.status_code == 200:
        data = response.json()
        derniers = sorted(data['matches'], key=lambda x: x['utcDate'], reverse=True)[:10]
        for match in derniers:
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            score_home = match['score']['fullTime']['home']
            score_away = match['score']['fullTime']['away']
            utc_date = match['utcDate']  # format : 2025-08-07T18:00:00Z
            utc_date = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
            py_tz = pytz.timezone('America/Port-au-Prince')
            localdate = utc_date.astimezone(py_tz)
            date = localdate.date()
            # convertir par exemple august=aout
            date_f = format_date(date, format='d MMMM y', locale='fr')
            heure = localdate.strftime('%H:%M')
            status = match['status']  # SCHEDULED, FINISHED, etc.
            competition = match['competition']['name']
            # ajouter le resultat
            resultat_tligb.append({
                'home': home_team,
                'away': away_team,
                'score': f"{score_home} - {score_away}",
                'status': status,
                'date': date_f,
                "heure": heure,
                'competition': competition
            })
        return resultat_tligb
    else:
        print("Erreur :")

def verifiernomutilisateur(nomutilisateur):
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select * from utilisateurs where nomutilisateur=?",(nomutilisateur,))
    result = req.fetchone()
    return result

def verifieremail(email):
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select * from utilisateurs where email=?", (email,))
    result = req.fetchone()
    return result

def inserercommentaire(id_utilisateurs,id_musiques,commentaire,date):
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    cursor.execute("insert into commentaires (id_utilisateurs,id_musiques,commentaire,date) values (?,?,?,?)",
                   (id_utilisateurs,id_musiques,commentaire,date))
    connection.commit()
    print('Votre commentaire a été ajouté avec succes..')
    connection.close()

def affichercommentaires(id_musiques):
    affcommentaire = []
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select u.nomutilisateur, c.id_utilisateurs, c.id_musiques, c.commentaire ,"
                         " c.date from commentaires c, utilisateurs u "
                         "where u.id = c.id_utilisateurs and c.id_musiques=? ORDER by c.id DESC limit 20", (id_musiques,))
    connection.commit()
    result = req.fetchall()
    for row in result:
        affcommentaire.append({'nomutilisateur':row[0], 'id_utilisateurs': row[1], 'commentaires': row[3], 'date': row[4]})
    return affcommentaire


def previsions_5_journees(lat, lon):
    # lat = 18.5392
    # lon = -72.335
    apikey = os.getenv('api_key_meteo')
    urlprev = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={apikey}&lang=fr"
    response1 = requests.get(urlprev)
    previsionsjours = []

    # Vérifier si la requête a réussi
    if response1.status_code == 200:
        data = response1.json()

        # Grouper par jour (une prévision par jour)
        forecasts_by_day = {}

        for forecast in data['list']:
            if isinstance(forecast['dt_txt'], str):
                date_str = forecast['dt_txt']
                date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                date_key = date_obj.date()

                if date_key not in forecasts_by_day:
                    forecasts_by_day[date_key] = forecast

        # Afficher les 6 premiers jours
        for date_key, forecast in list(forecasts_by_day.items())[:6]:
            # Format: "mercredi 20 janvier 2025"
            date_formatted = format_date(date_key, format="EEEE d MMMM y", locale='fr_FR')
            # Convertir la temperature de Kelvin en degre celsius
            cal_temp_cel = float(forecast['main']['temp']) - 273.15
            cal_temp_min = float(forecast['main']['temp_min']) - 273.15
            cal_temp_max = float(forecast['main']['temp_min']) - 273.15
            # formater les reponses avec un seul chiffre apres la virgule
            temp_celsius = f"{cal_temp_cel:.1f}"
            temp_min = f"{cal_temp_min:.1f}"
            temp_max = f"{cal_temp_max:.1f}"

            description = forecast['weather'][0]  # Description météo
            humidity = forecast['main']['humidity']
            wind_speed = int(forecast['wind']['speed']) * 3.6
            # Construire l'URL de l'icône
            icon_url = f"https://openweathermap.org/img/wn/{description['icon']}@2x.png"

            # print(f"  Humidité: {humidity}%, Vent: {wind_speed} m/s\n")
            previsionsjours.append({"dateprevjour": date_formatted,
                                    "temperature": temp_celsius,
                                    "temperaturemin": temp_min,
                                    "temperaturemax": temp_max,
                                    "description": description,
                                    "humidite": humidity,
                                    "vitessevent": wind_speed,
                                    "icon": icon_url
                                    })
        return previsionsjours

def previsions_prochains_heure(ville):
    apikey = os.getenv('api_key_meteo') # Remplacez par votre clé API
    previsionshoraires = [] # declaration de liste vide
    # Utiliser l'endpoint forecast pour les prévisions
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={ville}&appid={apikey}&units=metric"
    r = requests.get(url)
    # Vérifier si la requête a réussi
    if r.status_code == 200:
        data = r.json()

        # Récupérer les 6 prochaines prévisions (chaque entrée = 3 heures)
        previsions = data['list'][:8]

        # Extraire la température pour chaque prévision
        for i, prev in enumerate(previsions):
            tempnormal = prev['main']['temp']
            tempressenti = prev['main']['feels_like']
            dateheure = prev['dt_txt']  # Date et heure de la prévision
            description = prev['weather'][0]
            heure = datetime.strptime(dateheure, '%Y-%m-%d %H:%M:%S')
            icon_url = f"https://openweathermap.org/img/wn/{description['icon']}@2x.png"

            previsionshoraires.append({'horaire': heure.time().strftime('%H'),
                                       'tempsnormal': tempnormal,
                                      'tempsressenti': tempressenti,
                                       "icon": icon_url})
        return previsionshoraires
    else:
        print(f"Erreur: {r.status_code}")

def autrechannel(nomtele):
    recommandations = []
    nomtele_tv = str(nomtele).replace("-"," ")
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    requ = cursor.execute("select nom, url_stream, url_logo from channeltv where nom!=?", (nomtele_tv,))
    connection.commit()
    result_recom = requ.fetchall()
    # connection.close()
    for result_re in result_recom:
        recommandations.append({"chaine": result_re[0],
                                "urlstream": result_re[1],
                                "urllogo": result_re[2]
                                })

    return recommandations

# ###@app.after_request
# def ajout_csp(response):
#     response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'"
#     return response

@csrf.exempt
@app.route('/')
def accueil():
    api_key = os.getenv('api_key_nouvelles')
    pays_actualites = ['Haiti','Usa','France','Canada']
    keyword = random.choice(pays_actualites)
    stations = aff_stationradio()
    articles = []

    connection = True
    url_rss = 'https://www.lemonde.fr/rss/une.xml'
    feed = feedparser.parse(url_rss)
    entries = feed.entries
    # Retrouver des infos sur le site www.lemonde.fr par a son flux RSS
    try:
        for article in entries[:15]:
            image_url = None
            # Cherche une image dans 'media_content'
            if 'media_content' in article:
                for media in article['media_content']:
                    if 'url' in media:
                        image_url = media['url']
                        break  # Prend la première image
            # Ou dans les 'links' avec type image
            elif 'links' in article:
                for link in article['links']:
                    if link.get('type', '').startswith('image'):
                        image_url = link.get('href')
                        break
            dte = article.get('published') # le format fri, 10 oct 2025 11:10:25 +0200
            dt = datetime.strptime(dte, "%a, %d %b %Y %H:%M:%S %z")
            dtt = dt.replace(tzinfo=None)
            dateformatf = format_datetime(dtt , format="EEEE d MMMM y 'à' HH:mm a", locale='fr_FR')
            articles.append({'title': article.get('title'), 'link': article.get('link'), 'summary':article.get('summary'),'published': dateformatf, 'image': image_url})
    except Exception as e:
        print(f'Erreur API:{e}')
    # Création du dictionnaire de l'article

    return render_template('index.html', sections=['politique','radio'], stations=stations, articles=articles, pays=keyword,connection=connection)

    #

@csrf.exempt
@app.route('/stations-radios', methods=['GET'])
def stationradio():    # Récupération des stations par défaut
    stat = aff_stationradio()
    nomstations = []
    sections = ['statdefaut']  # par défaut, on affiche les radios locales
    if request.method == 'GET':
        namestation = request.args.get('stationradio', '').strip()
        if namestation:  # Si une recherche est faite
            try:
                # response = requests.get(f"https://de1.api.radio-browser.info/json/stations/search?name={namestation}")
                radio = RadioBrowser()
                response = radio.search(name=namestation, name_exact=True)
                if response:
                    for row in response:
                        nomstations.append({'name': row['name'], 'url': row['url_resolved'], 'icon': row['favicon'] or 'static/images/design1.jpg'})
                    # Parcourir la réponse
                    # Conditions
                    if nomstations:
                        sections = ['recherchestat']  # si résultats trouvés (Retourne une seule (1) section)
                    else:
                        sections = ['recherchestat', 'statdefaut']  # aucun résultat, on montre quand même les locales (Retourne (2) sections)
            # En cas d'erreur
            except Exception as e:
                print(f'Erreur lors de connexion API : {e}')
                sections = ['statdefaut']  # fallback si erreur API

    return render_template('stationradio.html',sections=sections,stat=stat, nomstations=nomstations)

@csrf.exempt
@app.route('/assistant-ia', methods=['GET','POST'])
def assistanceai():
    genai.configure(api_key=os.getenv('GEMINI_APIKEY'))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    reponses = []  # creation d'une liste vide
    # Formulaire (avec requete POST)
    if request.method=='POST':
        prompt = request.form.get('prompt')  # Récupérer les valeurs du champ texte
        def generate():
            try:
                response = model.generate_content(prompt, stream=True) # affichage en streaming tout comme chatgpt
                # conditions si le modèle génère des réponses
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                yield f"Erreur : {str(e)}"
    # on precise le type de conteu 'text/plain' ou text/event-stream
        return Response(generate(), mimetype='text/event-stream')
    return render_template('assistanceai.html')

@csrf.exempt
@app.route('/meteo', methods=['GET','POST'])
def affichermeteo():
    meteos = []
    previsionsjours = []
    previsionshoraires = []
    # verifier quel type de method utilise pour renvoyer le formulaire
    if request.method == 'GET':
        ville = request.args.get('ville')  # Récupérer les valeurs du champ texte (Ville)
        # conditions par defaut (si l'utilisateur n'a pas saisi une ville)
        if not ville:
            ville = "Port-au-Prince"
        try:
            apikey = os.getenv('api_key_meteo')
            # Faire une requête à l'API OpenWeatherMap
            url = f"https://api.openweathermap.org/data/2.5/weather?q={ville}&appid={apikey}&lang=fr&units=metric"  # Call de l'api
            r = requests.get(url)
            # Vérifier si la requête a réussi
            if r.status_code == 200:
                data = r.json()  # Récupérer les données en format JSON

                # Utilisation des données du fichier JSON
                lon_lat = data['coord']  # Afficher les coordonnées(latitude, longitude)
                # conditions meteo (pluie, soleil, nuage)
                weather = data['weather'][0]
                sys = data['sys']
                description = weather['description']
                icon_url = f"https://openweathermap.org/img/wn/{weather['icon']}@2x.png"

                # Traduction du français vers l'anglais
                # translator = GoogleTranslator(source='en', target='fr')
                # traduct_fr = translator.translate(description)
                # meteos = []
                # Créer un dictionnaire pour stocker les informations meteos
                meteos.append({"Longitude": lon_lat['lon'],
                               "Latitude": lon_lat['lat'],
                               "Temperature": f"{data['main']['temp']}",
                               "Temperatureressenti": round(data['main']['feels_like'], 1),
                               "Pression": f"{data['main']['pressure']}",
                                "Direction": f"{int(data['wind']['deg'] / 10)} degrés",
                               "Vitessekm": f"{round(data['wind']['speed'] * 3.6)}",
                               "Vitesse_m": f"{data['wind']['speed']} m/s",
                               "Humidite": data['main']['humidity'],
                               "description": f"{description}",
                               "Pays": f"{sys['country']}",
                               'ville': ville,
                               "icon": icon_url})
                # previsions pour les 5 prochains jours
                previsionsjours = previsions_5_journees(lon_lat['lat'], lon_lat['lon'])
                previsionshoraires = previsions_prochains_heure(ville)
                # return messages # retourner la valeur de la fonction
            else:
                # Gérer les erreurs
                if r.status_code == 404:
                    meteos.append({"reponse","Ville introuvable: f{ville}\n. Veuillez vérifier le nom et réessayer."})
                else:
                    meteos.append({"reponse", "Erreur:\nlors de la récupération des données météo. Veuillez réessayer plus tard."})
        except Exception as e:
            print("reponse",f"Erreur:lors de la récupération des données météo.{e}")

    return render_template('meteo.html', meteos=meteos, previsionsjours=previsionsjours, previsionshoraires=previsionshoraires)

@csrf.exempt
@app.route('/music')
def musiques():
    resultcompas = affichermusique_genre('compas')
    resultafro = affichermusique_genre('afrobeat')
    resultevangelique = affichermusique_genre("evangelique")
    return render_template('musiques.html', resultcompas=resultcompas, resultafro=resultafro, resultevangelique=resultevangelique)

@csrf.exempt
@app.route('/sports/score-en-direct')
def matchsencours():
    resultat_mpl, resultat_sa, resultat_fl1, resultat_mpd, resultat_bl1 = None, None, None, None, None
    try:
        resultat_mpl = matchsencours_premierleague()
        resultat_sa = matchsencours_seriea()
        resultat_fl1 = matchsencours_ligue1()
        resultat_bl1 = matchsencours_bundesliga()
        resultat_mpd = matchsencours_liga()
    except Exception as e:
        print('erreur')
    return render_template('score.html', section='championnat', resultat_mpl=resultat_mpl, resultat_sa=resultat_sa,
                           resultat_bl1=resultat_bl1, resultat_fl1=resultat_fl1, resultat_mpd=resultat_mpd)

@csrf.exempt
@app.route('/sports')
def sportactualites():
    section = request.args.get("section")
    championnat = request.args.get('championnat')
    # Créer une variable vide
    data = ''
    resultat ,image_base64,classementfrance, classementespagne, classementangleterre, classementitalie, classementallemagne = [],[],[],[],[],[],[]
    match_ligue1_auj, match_ligue1_dem, match_esp_auj, match_esp_dem, match_ang_auj = [], [], [], [], []
    match_ang_dem, match_ita_auj, match_ita_dem, match_all_auj, match_all_dem = [], [], [], [], []
    resultat_mpl, resultat_mpd, resultat_msa, resultat_mbl1, resultat_mfl1 = [],[],[],[],[]
    sportsactu = infos_sports()
    # # conditions
    if section == "classement" and championnat=="france":
        data = f'Classement du championnat {championnat}'
        classementfrance, image_base64 = classementchampionnat_france()
        match_ligue1_auj, match_ligue1_dem = calendrier_ligue1()
    elif section=='classement' and championnat=='espagne':
        data = f'Classement du championnat {championnat}'
        classementespagne, image_base64= classementchampionnat_espagne()
        match_esp_auj, match_esp_dem = calendrier_espagne()
    elif section=='classement' and championnat=='angleterre':
        data = f'Classement du championnat {championnat}'
        classementangleterre, image_base64 = classementchampionnat_angleterre()
        match_ang_auj, match_ang_dem = calendrier_angleterre()
    elif section=='classement' and championnat=='italie':
        data = f'Classement du championnat {championnat}'
        classementitalie, image_base64 = classementchampionnat_italie()
        match_ita_auj, match_ita_dem = calendrier_italie()
    elif section=='classement' and championnat=='allemagne':
        data = f'Classement du championnat {championnat}'
        classementallemagne, image_base64 = classementchampionnat_allemagne()
        match_all_auj, match_all_dem = calendrier_allemagne()
    elif section == "calendrier-matchs":
        data = "⚽ Calendrier des matchs"
        resultat = calendriermatch()
    elif section == "infos-equipes":
        data = "Infos sur les équipes ici..."
    return render_template('sports.html', sportsactu=sportsactu, championnat=championnat, data=data, classementfrance=classementfrance,image=image_base64,
                           match_ligue1_auj=match_ligue1_auj, match_ligue1_dem=match_ligue1_dem, classementespagne=classementespagne, match_esp_auj=match_esp_auj,
                           match_esp_dem=match_esp_dem, classementangleterre=classementangleterre, match_ang_auj=match_ang_auj,match_ang_dem=match_ang_dem, classementitalie=classementitalie,
                           match_ita_auj=match_ita_auj, match_ita_dem=match_ita_dem, classementallemagne=classementallemagne,match_all_auj=match_all_auj, match_all_dem=match_all_dem,
                           resultat=resultat, section=section, resultat_mpl=resultat_mpl)

# ✅ Route AJAX pour afficher l'heure
@csrf.exempt
@app.route('/heure')
def heure_actuelle():
    # dateheure = datetime.date.today()
    # # creation de compteur
    # hre = time.strftime('%I')
    # mnts = time.strftime('%M')
    # # sec = time.strftime('%S')
    # # dth = f'{hre}:{mnts}:{sec}'
    # # newdate = format_date(dateheure, format='EEEE dd MMMM yyyy', locale='fr_FR')
    # Récupérer la valeur du parametre (en section)
    hre = time.strftime('%H')
    mnts = time.strftime('%M')
    sec = time.strftime('%S')
    dth = f'{hre}:{mnts}:{sec}'
    return jsonify({"heure": dth})

@csrf.exempt
@app.route('/sports/match-termine')
def matchtermineend():
    resultat_tpl, resultat_tsa, resultat_tlig, resultat_tlig1, resultat_tligb = None, None, None, None, None
    try:
        resultat_tpl = matchtermine_pl()
        resultat_tlig = matchtermine_liga()
        resultat_tsa = matchtermine_seriea()
        resultat_tlig1 = matchtermine_ligue1()
        resultat_tligb = matchtermine_bundesliga()
    except Exception as e:
        print(f'Pas de donnees..{str(e)}')
    return render_template("match.html", resultat_tpl=resultat_tpl,
                           resultat_tlig=resultat_tlig, resultat_tsa=resultat_tsa,
                           resultat_tlig1=resultat_tlig1, resultat_tligb=resultat_tligb)

@csrf.exempt
@app.route('/sports/classement-buteurs')
def recuperertousbuteurs():
    buteurs_pl, buteurs_sa, buteurs_fl1, buteurs_pd, buteurs_bl1 = None,None,None,None,None
    scorer_europe = []
    try:
        buteurs_pl = recupererscorejoueur('PL')
        buteurs_sa = recupererscorejoueur('SA')
        buteurs_pd = recupererscorejoueur('PD')
        buteurs_fl1 = recupererscorejoueur('FL1')
        buteurs_bl1 = recupererscorejoueur('BL1')
        scorer_europe = scorer_europeen()
    except Exception as e:
        print('erreur')
    return render_template('classementbuteur.html', buteurs_pl= buteurs_pl,buteurs_pd=buteurs_pd, buteurs_sa=buteurs_sa,
                                                               buteurs_bl1=buteurs_bl1, buteurs_fl1=buteurs_fl1, scorer_europe=scorer_europe)

@csrf.exempt
@app.route('/music/<int:musique_id>/<slug>/')
def jouer_musique(musique_id, slug):
    conn = sqlite3.connect(lien_database)
    conn.row_factory = sqlite3.Row  # accès par nom de colonne
    cur = conn.cursor()
    # Recherche du titre avec slug transformé
    titre_recherche = slug.replace('-', ' ')
    cur.execute("SELECT * FROM musiques WHERE id=? AND titre LIKE ?", (musique_id, titre_recherche))
    musique = cur.fetchone()
    if not musique:
        return 'Musique introuvable ou erreur du serveur..', 404
    resultatmusique = {
        'id': musique['id'],
        'nom': musique['nom'],
        'url': musique['url'],
        'titre': musique['titre'],
        'image_url': musique['image_url'],
        'taille': musique['taille'],
        'date_modification': musique['date_modification'],
        'genre': musique['genre']
    }
    # Recommandations par artiste ou genre
    id = musique['id']
    id_musiques = musique['id']
    genre = musique['genre']
    url_m = musique['url']
    req = cur.execute('Select * from musiques where id !=? and genre=? order by random() limit 12', (id, genre))
    recommandations = req.fetchall()
    # Plus de contenu selon le style de musique (Rap)
    plus_contenu_musique = afficherpluscontenu(id, genre)
    conn.close()
    # récupérer les paroles pour cette chanson
    # Valeur par défaut
    paroles = "Paroles pas encore disponibles"
    # Afficher les commentaires
    affcommentaires = affichercommentaires(id_musiques)
    try:
        url = 'https://api.audd.io/'
        # files = {'file':open('ed_sheeran.mp3','rb')}
        params = {'url': url_m, 'api_token': os.getenv('api_audd'), 'return': 'lyrics, apple_music, spotify'}
        response = requests.get(url, params=params)
        data = response.json()
        paroles = data['result']['lyrics']['lyrics']
        print(paroles)
    except Exception as e:
        print(f"Erreur de connexion : {e}")
        paroles = "Paroles pas encore disponibles..."

    return render_template('lecteur.html', musique=resultatmusique, recommandations=recommandations,
                           plus_contenu_musique=plus_contenu_musique, chanson=paroles,  affcommentaires= affcommentaires)

@csrf.exempt
@app.route('/music/trending-songs')
def trendingsong():
    client_id = os.getenv('client_id_jamendo')
    url = f'https://api.jamendo.com/v3.0/tracks/?client_id={client_id}&format=json&limit=30&order=popularity_total'
    trending_songs = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # print(data)
            for id, (track) in enumerate(data['results'], 1):
                trending_songs.append({'id':id,'Titre': track['name'], "Artiste": track['artist_name'],
                                       "Ecouter": track['audio'],'duree':track['duration'],'image':track['album_image'],
                                       "Telecharger": track['audiodownload']})
        else:
            print("Erreur lors de la récupération des données.")
    except Exception as e:
        print(f'Erreur API{e}')
    return render_template('trending-song.html', trending_songs=trending_songs)

@csrf.exempt
@app.route('/music/new-track-music')
def newtrack():
    client_id = os.getenv('client_id_jamendo')
    url = f'https://api.jamendo.com/v3.0/tracks/?client_id={client_id}&format=json&limit=30&order=releasedate_desc'
    new_songs = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for id, (track) in enumerate(data['results'], 1):
                new_songs.append({'id':id,'Titre': track['name'], "Artiste": track['artist_name'],
                                       "Ecouter": track['audio'],'duree':track['duration'],'image':track['album_image'],
                                       "Telecharger": track['audiodownload']})
            # return new_songs
        else:
            print("Erreur lors de la récupération des données.")
    except Exception as e:
        print(f'Erreur API{e}')
    return render_template('new-song.html', new_songs=new_songs)

@csrf.exempt
@app.route('/music/news-artist')
def newsartist():
    news = []
    traduction = GoogleTranslator(source='en', target='fr')
    url = 'https://www.rollingstone.com/music/music-news/feed/'
    feed_liberation = feedparser.parse(url)
    contenu = feed_liberation.entries
    for row in contenu:
        if 'media_content' in row:
            image = row.media_content[0]['url']
        else:
            image = None
        news.append({"titre":row.title,"image-url":image, "published":row.published, 'description':traduction.translate(row.description), "lien":row.link})
    return render_template('artist.html', news=news)

@csrf.exempt
@app.route('/sante')
def infossante():
    url_rss = "https://lemonde.fr/sante/rss_full.xml"
    feed = feedparser.parse(url_rss)
    santes = feed.entries
    infos_santes = []
    try:
        for sante in santes:
            image_url = None
            if 'media_content' in sante:
                for media in sante['media_content']:
                    if 'url' in media:
                        image_url = media['url']
                        break
            elif 'links' in sante:
                for link in sante['links']:
                    if link.get('type', '').startswith('image'):
                        image_url = link.get('href')
                        break
            infos_santes.append({'title': sante.get('title'), 'link': sante.get('link'), 'summary': sante.get('summary'),'published': sante.get('published'), 'image': image_url})
    except Exception as e:
        print(f"Erreur de requete vers le fichier xml: {e}")
    return render_template('sante.html', santes=infos_santes)

@csrf.exempt
@app.route('/music/videos-youtube-trending')
def playvideosyoutube():
    apikey = os.getenv('api_youtubedata')
    youtube = build('youtube', 'v3', developerKey=apikey)
    request = youtube.videos().list(part='snippet, statistics', chart='mostPopular', regionCode='US', maxResults=20)
    response = request.execute()
    videosyoutube = []
    # Afficher les informations sur les vidéos le plus populaire sur youtube
    try:
        for video in response['items']:
            videosyoutube.append({"id": video['id'],"titre": video['snippet']['title'],
                                  'artiste':video['snippet']['channelTitle'],"vues": video['statistics'].get('viewCount', 'N/A')
                                  })
    except Exception as e:
        print(f'erreur {str(e)}')
    return render_template('videosyoutube.html', videosyoutube=videosyoutube)

@csrf.exempt
@app.route('/sciences')
def infossciences():
    url = 'https://www.lemonde.fr/sciences/rss_full.xml'
    feed = feedparser.parse(url)
    sciences = feed.entries
    infos_sciences = []  # pour stocker les resultats (par exemple : titre, lien, image, summary, date publication)
    try:
        for science in sciences:
            image_url = None
            if 'media_content' in science:
                for media in science['media_content']:
                    if 'url' in media:
                        image_url = media['url']
                        break
            elif 'links' in science:
                for link in science['links']:
                    if link.get('type', '').startswith('image'):
                        image_url = link.get('href')
                        break
            infos_sciences.append({'title': science.get('title'), 'link': science.get('link'), 'summary': science.get('summary'),'published': science.get('published'), 'image': image_url})
    except Exception as e:
        print(f"Erreur de requete vers le fichier xml: {e}")

    return render_template('sciences.html',sciences_=infos_sciences)

@csrf.exempt
@app.route('/live-tv')
def livetv():
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select * from channeltv limit 32")
    connection.commit()
    tv = []
    for result in req.fetchall():
        tv.append({'nomtv': result[1], 'url': result[2], 'images': result[3]})
    # transmettre les donnees du tv vers la page livetv.html
    return render_template('livetv.html', channeltv=tv)

@csrf.exempt
@app.route('/watch-tv/<nomtele>')
def lecturestreaming_tv(nomtele):
    channel_tv = []
    nomtele_tv = str(nomtele).replace("-"," ")
    recommandations = autrechannel(nomtele_tv)
    connection = sqlite3.connect('musique_bunny.db')
    cursor = connection.cursor()
    req = cursor.execute("select nom, url_stream, url_logo from channeltv where nom=?", (nomtele_tv,))
    connection.commit()
    result = req.fetchall()
    connection.close()
    for row in result:
        channel_tv.append({"nomtele": str(row[0]).replace("-", " "),"urlstream": row[1]})
    return render_template('watchtv.html', channel_tv=channel_tv, recommandations=recommandations)

@csrf.exempt
@app.route('/search', methods=['POST','GET'])
def searchmusic():
    query_mus = []
    titre = []
    chanson = []
    if request.method == 'GET':
        query_musique = request.args.get('query') # recuperer le mot cle tape par l'utilisateur
        query = f'%{query_musique}%'
        titre.append(query_musique)
        try:
            # connection a la base
            connection = sqlite3.connect(lien_database)
            cursor = connection.cursor()
            reqn = cursor.execute("Select * from musiques where lower(titre) like lower (?) or lower(nom) like lower (?)", (query, query))
            connection.commit()
            if reqn !=0:
                for row in reqn.fetchall():
                    query_mus.append({'id':row[0], 'nom': row[1], 'taille': row[2], 'datemodification': row[3],
                                      'url': row[4],'titre': row[5], 'image_url': row[6], 'genre': row[7]})
                    print('OK..')
            else:
                query_mus = "Cette chanson n'est pas disponible"
            connection.close()
        except Exception as e:
            print(f'Erreur de connexion {e}')
            query_mus = "Échec de connexion à internet"
    return render_template('search.html', query=query_mus, titre=''.join(titre))

@app.route('/login', methods=['GET', 'POST'])
def login():
    users = {"admin":"password"}
    if request.method == 'POST':
        nomutilisateur = request.form.get('username')
        motpasse = request.form.get('password')
        motpasse = hashlib.sha256(motpasse.encode()).hexdigest()
        connection = sqlite3.connect('musique_bunny.db')
        cursor = connection.cursor()
        req = cursor.execute("select * from utilisateurs where nomutilisateur=? and motpasse=?",
                       (nomutilisateur, motpasse))
        result = req.fetchone()
        print(result)
        if result is not None:
            session['user'] = result[1]
            # envoyer un mail à l'utilisateur a chaque fois, il est connecte
            # methode mail()
            return redirect(url_for('musiques'))
        else:
            return render_template('login.html', error='Identifiants incorrects')
    return render_template('login.html')
# @app.route('/sports/calendrier-match')

@app.route('/createaccount', methods=['GET','POST'])
def creationcompte():
    if request.method == 'POST':
        nomutilisateur = request.form.get('username')
        email = request.form.get('email')
        if verifiernomutilisateur(nomutilisateur) is not None:
            return render_template('createaccount.html', error="Le nom d'utilisateur est dejà utilisé.")
        elif verifieremail(email) is not None:
            return render_template('createaccount.html', error="L'adresse email est dejà utilisé.")
        # sinon
        else:
            motpasse = request.form.get('confirm_password')
            motpasse = hashlib.sha256(motpasse.encode()).hexdigest() # encrypter le mot de passe
            date = datetime.now() # date du jour
            d = date.date() # date du jour au format (01 sept 2025)
            date_format_fr = format_date(d, format='d MMMM y', locale='fr')
            connection = sqlite3.connect('musique_bunny.db')
            cursor = connection.cursor()
            cursor.execute("insert into utilisateurs (nomutilisateur,email,motpasse,datecreation) values (?,?,?,?)",
                                 (nomutilisateur, email,motpasse,date_format_fr))
            connection.commit()
            session['user'] = nomutilisateur # session de l'utilisateur
            flash("Votre compte a été crée avec succès...", "success")
            # envoyer un email de bienvenue a l'utilisateur
            htmlcontent = f"""
            <html>
            <body>
            <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ8w6m9T4Wlh8Gc4V-KzL00UHs9qax0cvwbog&s" style="height:220px; width:100%;"/>
            <p>
            Bienvenue sur <strong style="color:GREEN;font-size:14px;">Actuweb media</strong>
            </p>
                <p style="color:#333;background-color:black;">
                            Nous vous remercions d'avoir créé un compte sur notre site web actuwebmedia.<br/>.
                            <br/>Nous sommes ravis de vous accueillir au sein de notre communauté de passionnés de musique.
                            <br/>Vous pouvez désormais laisser vos commentaires et avis sur les différentes musiques présentes sur notre plateforme.
                            <br/>N'hésitez pas à nous faire part de vos impressions et de vos coups de cœur. Votre feedback nous est précieux pour enrichir notre catalogue musical."
                            <br/>Si vous avez la moindre question, n'hésitez pas à nous contacter. Nous restons à votre écoute.
                            <br/><br/>Cordialement, L'équipe actuwebmedia..
                            <br/>
                            </p>
                            <a href="https://www.actuwebmedia.it.com/unsubscribe?email="{email}"> Se désabonner </a>

            </body>
            </html>
            """
            # create mail object
            mail = mt.Mail(
            sender = mt.Address(email="info@actuwebmedia.it.com", name="notifications"),
            to = [mt.Address(email=email)],
            subject="Message de Bienvenue",
            text = "Bienvenue",
            html = htmlcontent
        )

            # create client and send
            client = mt.MailtrapClient(token=os.getenv('api_mailtrap'))
            if client:
                client.send(mail)
                print("Envoyé...")
            else:
                print('échec...')
            # mail.send(msg) # methode qui renvoi l'email
            return redirect(url_for('musiques'))
    else:
        return render_template('createaccount.html', error='Verifier si tous les champs sont bien remplies.')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/create-account')
def showpageaccount():
    return render_template('createaccount.html')


@app.route('/music/<int:musique_id>/<titre>/', methods=['GET', 'POST'])
def ajoutercommentaire(musique_id, titre):
    commentaires = []
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        commentaire = request.form.get('comment')
        # user
        nomutilisateur = session['user']
        connection = sqlite3.connect('musique_bunny.db')
        cursor = connection.cursor()
        req = cursor.execute("select id from utilisateurs where nomutilisateur=?",(nomutilisateur,))
        result = req.fetchone()
        id_utilisateurs = result[0] # recuperer l'id user
        conn = sqlite3.connect(lien_database)
        conn.row_factory = sqlite3.Row  # accès par nom de colonne
        cur = conn.cursor()
        # Recherche du titre avec slug transformé
        titre_recherche = titre.replace('-', ' ')
        cur.execute("SELECT * FROM musiques WHERE id=? AND titre LIKE ?", (musique_id, titre_recherche))
        musique = cur.fetchone()
        if not musique:
            return '<p style="text-align:center;">Musique introuvable ou erreur du serveur..</p>', 404
        resultatmusique = {
            'id': musique['id'],
            'nom': musique['nom'],
            'url': musique['url'],
            'titre': musique['titre'],
            'image_url': musique['image_url'],
            'taille': musique['taille'],
            'date_modification': musique['date_modification'],
            'genre': musique['genre']
        }
        # Recommandations par artiste ou genre
        id = musique['id']
        genre = musique['genre']
        url_m = musique['url']
        req = cur.execute('Select * from musiques where id !=? and genre=? order by random() limit 12', (id, genre))
        recommandations = req.fetchall()
        # Plus de contenu selon le style de musique (Rap)
        plus_contenu_musique = afficherpluscontenu(id, genre)
        conn.close()
        # récupérer les paroles pour cette chanson
        # Valeur par défaut
        paroles = "Paroles pas encore disponibles"
        # Afficher les commentaires
        id_musiques = musique['id']
        affcommentaires = affichercommentaires(id_musiques) # methode affichage de commentaires
        # Convertir chaque Row en dictionnaire
        affcommentaires_list = [dict(c) for c in affcommentaires]
        # Exemple pour recommandations
        recommandations_list = [dict(r) for r in recommandations]
        # date du jour
        dat = datetime.now()
        date = dat.strftime('%d-%m-%Y %H:%M') # changer le format en date et heure
        try:
            url = 'https://api.audd.io/'
            # files = {'file':open('ed_sheeran.mp3','rb')}
            params = {'url': url_m, 'api_token': os.getenv('api_audd'),'return': 'lyrics, apple_music, spotify'}
            response = requests.get(url, params=params)
            data = response.json()
            paroles = data['result']['lyrics']['lyrics']
            print(paroles)
        except Exception as e:
            print(f"Erreur de connexion : {e}")
            paroles = "Paroles pas encore disponibles..."

        commentaires.append({'nomutilisateur': session['user'], 'commentaires': commentaire, 'date': date}) # pour afficher le dernier commentaire
        inserercommentaire(id_utilisateurs, id_musiques, commentaire, date) # insertion de commentaire dans une base
        return jsonify({'message': 'Votre commentaire a été ajouté avec succès...',
                        'commentaires':commentaires, 'affcommentaires':affcommentaires_list,
                        'musique' : resultatmusique, 'recommandations': recommandations_list,
                      'plus_contenu_musique':plus_contenu_musique, 'chanson':paroles
                        })
        # return render_template('lecteur.html', commentaires=commentaires, affcommentaires=affcommentaires, musique=resultatmusique, recommandations=recommandations,
        #                    plus_contenu_musique=plus_contenu_musique, chanson=paroles)
    else:
        print('commentaire non envoye..')


# pour ajouter l'année en cours au pied de page
@app.context_processor
def inject_year():
    return {"year": datetime.now().year}


@app.context_processor
def inject_request():
    return dict(request=request)


@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')


# @app.route('/robots.txt')
# def robots():
#     return send_from_directory('static','robots.txt', mimetype='text/plain')

@app.route('/googleadf9f2a8534e6c04.html')
def google_verification():
    return app.send_static_file('googleadf9f2a8534e6c04.html')

# fonction principale
if __name__ == '__main__':
    app.run(debug=True, use_reloader=True, port=5005)

