from itertools import groupby
from app.common.function import diff_commonPrefix
from flask import Blueprint
from flask import Flask, render_template, session, request, flash, redirect, url_for, Response, abort, jsonify, \
    send_file
import socket
import os
import random
import copy
# from app.global_var import munhak_rows_data
from flask_sqlalchemy import SQLAlchemy, Model
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import base64
from collections import namedtuple
from flask_restful import Api, Resource, reqparse
from sqlalchemy import desc, asc
import uuid

# from app.common.encrypt import simpleEnDecrypt


from config import credentials, SECRET_KEY
from app.cache import cache
from app.common.function import fetch_spread_sheet, send_discord_alert_log, edit_distance
from app.db import *
from datetime import datetime

quiz_bp = Blueprint('quiz', __name__)


@quiz_bp.route('/')
def index():
    quiz_data = cache.get("quiz_data")

    quiz_rows = copy.deepcopy(quiz_data)

    return render_template("index_new.html")


def make_quiz(quiz_rows, not_selected_quiz_rows):
    # import time
    # start = time.time()  #

    target_quiz_row = random.choice(not_selected_quiz_rows)
    correct_sentence = target_quiz_row["quiz"]["correct"]
    if random.random() <= 0.5:



        key_list = []

        stack = []
        f = False
        space_count = 0
        for c in target_quiz_row["quiz"]["problem"]:
            if c == "[":
                f = True
            elif f is True:
                if c == "]":
                    key = [x.strip() for x in "".join(stack).split("/")]
                    key_list.append({
                        "nth_word": space_count,
                        "key": key
                    })
                    stack.clear()
                    f = False
                else:
                    stack.append(c)
            elif c == " ":
                space_count += 1

        target_key = random.choice(key_list)

        random.shuffle(target_key["key"])

        wrong_key = None
        correct_key = None
        for key in target_key["key"]:
            temp_sentence = " ".join(correct_sentence.split()[:target_key["nth_word"]]) + " " + key + " " + \
                            " ".join(correct_sentence.split()[target_key["nth_word"] + len(key.split()):])
            print(temp_sentence)


            if temp_sentence == correct_sentence:
                correct_key = key
            elif wrong_key is None:
                wrong_key = key
                print(len(wrong_key.split()))
                print(wrong_key)

        wrong_sentence = " ".join(correct_sentence.split()[:target_key["nth_word"]]) + " " + wrong_key + " " + \
                         " ".join(correct_sentence.split()[target_key["nth_word"] + len(correct_key.split()):])

        quiz_data = {
            "quiz_seq": target_quiz_row["quiz_seq"],
            "correct_sentence": correct_sentence,
            "wrong_sentence": wrong_sentence,
            "wrong_key": wrong_key,
            "wrong_nth_word": list(range(target_key["nth_word"], target_key["nth_word"] + len(wrong_key.split()), 1)),
            "correct_nth_word": list(
                range(target_key["nth_word"], target_key["nth_word"] + len(correct_key.split()), 1)),
            "type": "choose"
        }



    else:
        problem_sentence = ""

        key_list = []
        correct_list = []
        stack = []
        f = False
        space_count = 0
        for c in target_quiz_row["quiz"]["problem"]:

            if c == "[":
                f = True
            elif f is True:
                if c == "]":
                    key = [x.strip() for x in "".join(stack).split("/")]
                    random.shuffle(key)
                    key_list.append({
                        "nth_word": space_count,
                        "key": key
                    })
                    stack.clear()
                    f = False
                    problem_sentence += "<빈칸>"



                else:
                    stack.append(c)
            elif c == " ":
                space_count += 1
                problem_sentence += c
            else:
                problem_sentence += c



        temp = problem_sentence.split("<빈칸>")
        for i in range(len(temp) - 1):
            correct_key = correct_sentence.split(temp[i])[1].split(temp[i+1])[0]
            correct_list.append(correct_key)


        print(correct_list)
        quiz_data = {
            "quiz_seq": target_quiz_row["quiz_seq"],
            "problem_sentence": problem_sentence,
            "correct_sentence" : target_quiz_row["quiz"]["correct"],
            "key_list" : key_list,
            "correct_list" : correct_list,
            "type": "option"
        }
        # print(correct_sentence)
        # print(key_list)


    return quiz_data


@quiz_bp.route('/get-quiz', methods=["GET", "POST"])
def get_quiz():
    # import time
    # time.sleep(1)
    # time.sleep(1)
    if "quiz_source" not in session:
        session["quiz_source"] = "all"
    else:
        quiz_source = session["quiz_source"]

    quiz_rows_data = cache.get("quiz_data")

    # if quiz_source == "s1":
    #     munhak_rows_data = [munhak_row for munhak_row in munhak_rows_data if
    #                         munhak_row["source"].split()[-1] != "수능특강" and munhak_row["source"].split()[-1] != "수능완성"]
    # elif quiz_source == "s2":
    #     munhak_rows_data = [munhak_row for munhak_row in munhak_rows_data if
    #                         munhak_row["source"].split()[-1] == "수능특강" or munhak_row["source"].split()[-1] == "수능완성"]
    #
    # if "is_end" in session and session["is_end"] is True:
    #     session["quiz_count"] = 0
    #     session["total_munhak"] = len(munhak_rows_data)
    #     session["solved_quiz"] = []
    #     session["current_munhak"] = None
    #     session["is_end"] = False
    #
    # if "quiz_count" not in session:
    #     session["quiz_count"] = 0
    #     session["total_munhak"] = len(munhak_rows_data)
    if "solved_quiz" not in session:
        session["solved_quiz"] = []
    # session["result"] = None
    #
    # quiz_no = session["quiz_count"] + 1
    solved_quiz = session["solved_quiz"]
    #
    # if "_id" not in session:
    #     session["_id"] = uuid.uuid4()

    if "current_quiz" not in session or session["current_quiz"] is None:

        # munhak_rows = Munhak.query.filter_by(is_available=True).all()

        quiz_rows = copy.deepcopy(quiz_rows_data)

        not_solved_quiz_rows = [quiz_row for quiz_row in quiz_rows if
                                quiz_row["quiz_seq"] not in solved_quiz]

        if len(not_solved_quiz_rows) == 0:  # 다 맞았을 때
            session["solved_quiz"] = []
            not_solved_quiz_rows = quiz_rows

        quiz_data = make_quiz(quiz_rows, not_solved_quiz_rows)

        session["current_quiz"] = quiz_data

        if quiz_data["type"] == "choose":
            data = {
                "wrong_sentence": quiz_data["wrong_sentence"],
                "type": quiz_data["type"]
            }
        elif quiz_data["type"] == "option":
            data = {
                "problem_sentence": quiz_data["problem_sentence"],
                "key_list": quiz_data["key_list"],
                "type" : quiz_data["type"]
            }

        return render_template("quiz.html", data=data)
    else:
        if session["current_quiz"]["type"] == "choose":

            data = {
                "wrong_sentence": session["current_quiz"]["wrong_sentence"],
                "type": session["current_quiz"]["type"],
            }
        elif session["current_quiz"]["type"] == "option":
            data = {
                "problem_sentence": session["current_quiz"]["problem_sentence"],
                "key_list": session["current_quiz"]["key_list"],
                "type": session["current_quiz"]["type"]
            }
        # print(hint)

        return render_template("quiz.html", data=data)


@quiz_bp.route('/play')
def quiz():
    args = request.args
    re = "re" in args and args["re"] == "true"
    s1 = "s1" in args and args["s1"] == "false"
    s2 = "s2" in args and args["s2"] == "false"
    if re:
        if s1 and not s2:
            session["quiz_source"] = "s2"
        elif not s1 and s2:
            session["quiz_source"] = "s1"
        else:
            session["quiz_source"] = "all"

        session["quiz_count"] = 0
        session["solved_quiz"] = []
        session["current_munhak"] = None
        session["is_end"] = False
        return redirect(url_for("quiz.quiz"))

    return render_template("quiz_container.html")


@quiz_bp.route("/answer", methods=["GET", "POST"])
def answer():
    print(session)


    current_quiz = session["current_quiz"]
    if current_quiz is None:
        return abort(401)



    session["solved_quiz"].append(session["current_quiz"]["quiz_seq"])
    correct_sentence = current_quiz["correct_sentence"]
    if current_quiz["type"] == "choose":
        wrong_part = " ".join(current_quiz["wrong_sentence"].split()[
                              current_quiz["wrong_nth_word"][0]: current_quiz["wrong_nth_word"][-1] + 1])
        correct_part = " ".join(current_quiz["correct_sentence"].split()[
                              current_quiz["wrong_nth_word"][0]: current_quiz["wrong_nth_word"][-1] + 1])

        c = 0
        for a,b in zip(wrong_part.split(), correct_part.split()):
            if a == b :
                c += 1
            else:
                break

        print(wrong_part, correct_part)

        option = request.form.get("option", None)
        print(option)

        if option is None or (not type(option) != int):
            return abort(400)
        option = int(option)

        if option in current_quiz["wrong_nth_word"][c:]:
            print("success")
            return get_result(True, "choose")
        else:
            print("no!")
            return get_result(False, "choose")



        # wrong_index = diff_commonPrefix(correct_sentence, wrong_sentence)
        # space_count = 0
        # f = False
        # start_pos, last_pos = -1, -1
        # for i, c in enumerate(wrong_sentence):
        #     if c == " ":
        #         space_count = space_count + 1
        #         if f is True:
        #             last_pos = i - 1
        #             break
        #         if space_count == option:
        #             start_pos = i + 1
        #             f = True
        #
        # print(start_pos, last_pos + len(session["current_quiz"]["wrong_key"]))
        # print(wrong_index)
        # if any([True for x in range(len(session["current_quiz"]["wrong_key"])) if
        #         start_pos <= wrong_index + x <= last_pos]):
        #     print("success")
        #     return get_result(True, "choose")
        # else:
        #     print("no!")
        #     return get_result(False, "choose")


    elif current_quiz["type"] == "option":

        option = request.get_json()["option"]
        print(option)
        print(request.json)
        if option is None:
            return abort(400)
        answer_sentence = current_quiz["problem_sentence"]
        for i, word in option.items():
            print(word)
            answer_sentence = answer_sentence.replace("<빈칸>", word, 1)
        print(answer_sentence)
        print(correct_sentence)
        if answer_sentence == correct_sentence:
            return get_result(True, "option")
        else:
            return get_result(False, "option")

def get_result(is_success, type):

    if type == "choose":

        data = {
            "wrong_sentence": session["current_quiz"]["wrong_sentence"],
            "correct_sentence": session["current_quiz"]["correct_sentence"],
            "wrong_nth_word": session["current_quiz"]["wrong_nth_word"],
            "correct_nth_word": session["current_quiz"]["correct_nth_word"],
            "is_success": is_success,
            "type": type
        }

    if type == "option":
        data = {
            "problem_sentence" : session["current_quiz"]["problem_sentence"],
            "correct_sentence" : session["current_quiz"]["correct_sentence"],
            "wrong_nth_word": [],
            "correct_nth_word": [],
            "key_list" : session["current_quiz"]["key_list"],
            "correct_list": session["current_quiz"]["correct_list"],
            "is_success": is_success,
            "type": type
        }
    session["current_quiz"] = None
    return render_template("result.html", data=data)

#
#
# @quiz_bp.route("/result", methods=["GET", "POST"])
# def result():
#     if "result" not in session:
#         return redirect(url_for("quiz.index"))
#
#     if "quiz_count" in session and session["quiz_count"] >= 10:
#         send_discord_alert_log(f"{session['quiz_count']}개를 맞혔어요!")
#
#     is_success = session["result"]
#     session["is_end"] = True
#
#     # session["quiz_count"] = 0
#     # session["solved_quiz"] = []
#     # session["current_munhak"] = None
#
#     is_best_record = False
#
#     if "user" in session:
#         user_seq = session["user"]["user_seq"]
#         old_record_row = QuizRanking.query.filter_by(user_seq=user_seq).first()
#         if old_record_row is None:
#             if session["quiz_count"] >= 1:
#                 record_row = QuizRanking(user_seq=user_seq, score=session["quiz_count"], record_date=datetime.now())
#                 db.session.add(record_row)
#                 db.session.commit()
#                 is_best_record = True
#         else:
#             if session["quiz_count"] >= 1 and session["quiz_count"] > old_record_row.score:
#                 old_record_row.score = session["quiz_count"]
#                 db.session.commit()
#                 is_best_record = True
#
#     correct = session["correct"]
#     data = {
#         "is_success": is_success,
#         "solved_count": session["quiz_count"],
#         "correct": correct,
#         "current_munhak": session["current_munhak"],
#         "is_best_record": is_best_record,
#         "correct_option": session["options"][correct]
#     }
#     print(session["options"][correct])
#
#     print(data)
#     return render_template("result.html", data=data)
