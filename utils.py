import numpy as np
import codecs, json

score_file_path_4 = "score4.txt"
score_file_path_8 = "score8.txt"

qmatrix_file_path_4 = "grade4-qmatrix.txt"
qmatrix_file_path_8 = "grade8-qmatrix.txt"

def read_score(grade):
    if grade == 4:
        file_path = score_file_path_4
    elif grade == 8:
        file_path = score_file_path_8
    else:
        file_path = score_file_path_4

    score = np.loadtxt(file_path, dtype = int)
    if (score.shape == (0,)):
        score = np.empty([0, 42], dtype = int)
    return score

def add_score(grade, score):
    if grade == 4:
        file_path = score_file_path_4
    elif grade == 8:
        file_path = score_file_path_8
    else:
        file_path = score_file_path_4

    score = score.replace('[', '')
    score = score.replace(']', '')
    score = score.replace('\n', '')
    score += '\n'
    with open(file_path, "a") as myfile:
        myfile.write(score)

def read_q_matrix(grade):
    if grade == 4:
        file_path = qmatrix_file_path_4
    elif grade == 8:
        file_path = qmatrix_file_path_8
    else:
        file_path = qmatrix_file_path_4

    qmatrix = np.loadtxt(file_path, dtype = int)
    return qmatrix.T
