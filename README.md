# EduChatBot - Ein KI-basierter Lernassistent

## Einleitung

Dieses Repository enthält den Quellcode für das Backend eines EduChatBot-Systems, das auf Flask, einer Vektordatenbank und der OpenAI API (ChatGPT) basiert. Das Projekt wurde im Rahmen des REACT Förderprojekts an der Eckener-Schule entwickelt, um Schülerinnen und Schülern sowie Lehrkräften eine innovative und effektive Lernunterstützung zu bieten. Die entwickelte Softwarelösung ermöglicht den Zugriff auf KI-gestützte Antworten und interaktive Dialoge.

## Zielsetzung

Das Ziel dieses Projekts ist es, das fortschrittliche Sprachmodell ChatGPT durch den Einsatz von Retrieval-Augmented Generation (RAG) für den Bildungsbereich zu adaptieren. Durch die Integration spezifischer Unterrichtsdaten in eine Vektordatenbank kann der Chatbot präzisere und kontextbezogene Antworten generieren.

## Projektstruktur

### Backend

- Framework: Flask (Python)
- API: REST-API zur Kommunikation mit ChatGPT
- Datenbank: SQL-Datenbank zur Speicherung von Unterrichtsinhalten, die in eine Vektordatenbank überführt werden
- Anonymisierte Datenerfassung: Speicherung und Analyse der Interaktionen zur kontinuierlichen Verbesserung des Systems

### Weitere Repositories

Das Moodle-Plugin, das für die Integration in das LMS (Learning Management System) verantwortlich ist, befindet sich in einem separaten Repository. 

## Installation

### Voraussetzungen

- Docker
- Python 3.11+
- Flask

### .env Datei

Erstelle eine .env Datei im Wurzelverzeichnis und passe die erforderlichen Umgebungsvariablen an.

### Schritt-für-Schritt Anleitung

1. Repository klonen
   git clone https://github.com/dein-username/EduChatBot.git
   cd EduChatBot

2. Docker-Container erstellen
   docker-compose up --build

3. Datenbank migrieren
   flask db upgrade

4. Domain und E-Mail in der docker-compose.yml Datei anpassen

## Nutzung

### Admin- und Lehrer-Frontends

#### Admin-Frontend

- Nutzerverwaltung: Hinzufügen, Bearbeiten und Löschen von Nutzern
- Kurs- und Fachverwaltung: Managen von Kursen und Fächern
- API-Schlüssel Verwaltung: Einstellen des OpenAI API-Schlüssels
- Fehleranalyse: Einsicht auf Bugs und Fehler
- Chatverlauf-Analyse: Einsehen und Analysieren von Chatverläufen

#### Lehrer-Frontend

- Kurs- und Fachverwaltung: Hinzufügen, Bearbeiten und Löschen von Kursen und Fächern
- Informationsmanagement: Verwalten und Aktualisieren von Unterrichtsinhalten
- Chatverlauf-Analyse: Einsehen von Schüler-Chatverläufen

### Funktionalitäten

- Benutzerdefinierte Prompts: Erlauben dem Chatbot, Fragen nur auf Basis der bereitgestellten Daten zu beantworten
- Vektordatenbank: Speicherung und Zuordnung von Unterrichtsinhalten mittels Embeddings
- Anonymisierte Datenspeicherung: Schutz der Privatsphäre der Nutzer und Analyse zur Verbesserung des Chatbots

## Herausforderungen und Weiterentwicklungen

### Herausforderungen

- Fine-Tuning vs. RAG: Entscheidung zugunsten von RAG für präzisere Antworten
- Frontend-Komplexität: Vereinfachung des Lehrer-Frontends
- Deployment mit Docker: Anpassungen für eine reibungslose Serverbereitstellung

### Mögliche Weiterentwicklungen

- Token-Limitation: Einführung von Maßnahmen zur Tokensparung
- Dynamische Einbindung des Chats: Overlay-Chatfenster und benutzerdefinierte Prompts
- Multimediale Inhaltsverwaltung: Upload von Bildern, Texten, PDFs und Videos
- Asynchrone Verarbeitung: Optimierung der Leistung bei gleichzeitiger Nutzung
- Direktes Fragenstellen in Moodle: Textmarkierung und Fragestellung direkt in Moodle
- Zentralisierung von Lerninhalten: Bereitstellung sämtlicher Lerninhalte über eine zentrale Plattform

## Lizenz

Dieses Projekt steht unter der Open-Source-Lizenz und ist Teil der Open Educational Resources (OER).

## Entwickelt von

Neox Studios GmbH  
Lise-Meitner-Straße 2  
24941 Flensburg  
+49 (0) 461 408 329 22  
kontakt@neox-studios.de  
www.neox-studios.de

## Kontakt

RBZ Eckener-Schule Flensburg
Friesische Lücke 15, 
24937 Flensburg
https://www.eckener-schule.de/

