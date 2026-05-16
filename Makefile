p = 48
m = "comentari"

all: crea_graf_i_sol view 

crea_graf_i_sol: 
	pixi run python src/graph.py puzzles/$(p).json
	pixi run python src/solve.py puzzles/$(p).graphml
	
view: 
	pixi run python src/3D_view.py puzzles/$(p).graphml puzzles/$(p).sol.json

gif:
	pixi run python src/movie.py puzzles/$(p).json puzzles/$(p).sol.json puzzles/$(p).gif
	open -a "Safari" puzzles/$(p).gif

play: 
	pixi run python src/play.py puzzles/$(p).json

descarrega:
	pixi run python src/download.py

git:
	git add .
	git commit -m "$(m)"
	git push origin main

esborra:
	rm puzzles/$(p).graphml puzzles/$(p).sol.json
	