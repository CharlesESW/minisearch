My first attempt at a small search engine, available at https://search.246802468.xyz.

# How to run?
1. copy .env.example into .env and set the values. you will probably be locally hosting so I have left the examples for that i think
2. then you will need to run 'docker compose up -d' to get the typesense server running
3. before you can run the crawldexer we will need to setup our python environment (i hope you have python installed)
4. first run "python -m venv venv" to setup the venv and then "source venv/bin/activate" to enter the venv
5. run pip install -r requirements.txt, then you will have everything and can run the crawldexer
7. before you run the frontend you need to copy env.js.example (sorry there's more than one file) to env.js and set the values. To get the value for the public API key run "curl -X POST "http://localhost:8108/keys" -H "X-TYPESENSE-API-KEY: <admin_api_key>" -H "Content-Type: application/json" -d '{ "description": "Search-only key for frontend", "actions": ["documents:search"], "collections": ["webpages"]}'" in the terminal
8. once you've set those values you can then run 'bash serverrun.sh' and it will startup on whatever port I wrote in there where you can access it from. For this you will need the 'screen' package, its called that on apt good luck on other distros
9. It should now work? i think that's all the setup steps but please let me know if it does not work

feel free to contribute cos you might be able to tell the codebase is kinda dodgy and this might be useful to some people
