p = 50
m = "comentari"
score = auto
token = "019d90b1-6aab-7000-a340-4ba3cc79679a"

all: graf_sol view 

graf_sol: 
	pixi run python src/graph.py puzzles/downloads/$(p).json
	pixi run python src/solve.py puzzles/downloads/$(p).graphml
	
view: 
	pixi run python src/3D_view.py puzzles/downloads/$(p).graphml puzzles/downloads/$(p).sol.json

gif:
	pixi run python src/movie.py puzzles/downloads/$(p).json puzzles/downloads/$(p).sol.json puzzles/downloads/$(p).gif
	open -a "Safari" puzzles/downloads/$(p).gif

play: 
	pixi run python src/play.py puzzles/downloads/$(p).json

eval:
	pixi run python src/eval.py puzzles/downloads/$(p).json

rate:
	pixi run python src/rate.py $(p) $(score) $(token)

descarrega:
	pixi run python src/download.py

git:
	git add .
	git commit -m "$(m)"
	git push origin main

esborra:
	rm -f puzzles/downloads/*.json puzzles/index.json
