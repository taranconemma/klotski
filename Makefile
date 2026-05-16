all: crea_graf_i_sol

crea_graf_i_sol: 
	pixi run python src/graph.py puzzles/sample1.json
	pixi run python src/solve.py puzzles/sample1.graphml
	
view: 
	pixi run python src/3D_view.py puzzles/sample1.graphml puzzles/sample1.sol.json

gif:
	pixi run python src/movie.py puzzles/sample1.json puzzles/sample1.sol.json puzzles/sample1.gif	open puzzles/sample1.gif
	open -a "Safari" puzzles/sample1.gif

descarrega:
	