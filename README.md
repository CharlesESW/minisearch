My first attempt at a small search engine, available at https://search.246802468.xyz.

# How to run?
1. copy .env.example into .env and set the values. you will probably be locally hosting so I have left the examples for that i think
2. then you will need to run 'docker compose up -d' to get the typesense server running
3. once the server is running you are free to run the crawldexer
4. before you run the frontend you need to copy env.js.example (sorry there's more than one file) to env.js and set the values. To get the value for the public API key run "curl -X POST "http://localhost:8108/keys" -H "X-TYPESENSE-API-KEY: <admin_api_key>" -H "Content-Type: application/json" -d '{ "description": "Search-only key for frontend", "actions": ["documents:search"], "collections": ["webpages"]}'" in the terminal
5. once you've set those values you can then run 'bash serverrun.sh' and it will startup on whatever port I wrote in there where you can access it from
6. It should now work? i think that's all the setup steps but please let me know if it does not work

feel free to contribute cos you might be able to tell the codebase is kinda dodgy and this might be useful to some people idk 
