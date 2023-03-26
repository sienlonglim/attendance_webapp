# scraping_attendance project
## This side project is exclusively for TFIP-2022.
The purpose of the project is to address the pain point we previously experienced, which was the difficulty in identifying who has not signed the attendance on the SSG website.<br>
The exitsing code (as of 7 Mar 2023) is functional. Nonetheless, there are two/more limitations. First, it is a bit slow; second, there is no user interface, but just Python codes.<br>
I encourage all the collaborators to make any improvements you see fit. <br>
-- Zhiyuan, 7/Mar/2023, at DigiPen Singapore

Improvements:
1. Used flask and bootstrap to create a user interface for the project.
2. Modified the code to just use requests and access the api to return a json file, instead of selenium
3. For ease of access, the webapp is hosted on [pythonanywhere free hosting](http://natuyuki.pythonanywhere.com/) - however the hosting site does not allow selenium or requests to skillsfuture yet, requesting for them to whitelist the webpage.
4. Changed to using sets to find the absentees. -- Sien Long 14/Mar/2023
5. Migrated name list to off-site SQL database, credentials are in another file (config.py) -- Rong Yi 14/Mar/2023

Further improvements:
1. Stored namelists in a local database instead of on-script, removed all sensitive information.
2. Added an optional script to use pywhat to send whatsapp message instead, to update the classgroup.
-- Sien Long 24/Mar/2023
