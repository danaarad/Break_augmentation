import os
import csv
import random
from google.cloud import translate

# General Settings
PROJECT_ID = "double-kite-276312"
INPUT_FILE = "original_train.csv"
INPUT_FILE_ID_INDEX = 0
INPUT_FILE_QUESTION_INDEX = 1
INPUT_FILE_DECOMP_INDEX = 2

# Part 1 - testing multiple languages
LANG_TEST_FILE = "test_langs.tsv"
NUM_OF_SAMPLES_FOR_LANG_TEST = 50
ENGLISH_LANG_CODE = "en"
TARGET_LANGS_TO_TEST = ["he", "de", "ru", "ja"]

# Part 2 - generating new samples using german
#  as the first options and japanese as the fallback
NEW_TRAIN_FILE = "train.tsv"
FULL_NEW_SAMPLES_FILE = "new_samples_full.csv"
FULL_NEW_SAMPLES_FILE_WITH_FALLBACK = "new_samples_full_with_fallback.csv"
STATS_FILE = "stats.csv"
TARGET_LANG = "de"
FALLBACK_TARGET_LANG = "ja"


class Translator:
    def __init__(self, project_id):
        self.project_id = project_id
        self.client = translate.TranslationServiceClient()
        self.parent = self.client.location_path(project_id, "global")

    def translate(self, text, src_lang, dst_lang):
        response = self.client.translate_text(
                parent=self.parent,
                contents=[text],
                mime_type="text/plain",
                source_language_code=src_lang,
                target_language_code=dst_lang,
        )
        return response.translations[0].translated_text

    def round_trip_translate(self, text, middle_lang):
        translation = self.translate(text, ENGLISH_LANG_CODE, middle_lang)
        translation = self.translate(translation, middle_lang, ENGLISH_LANG_CODE)
        return translation.lower()


def get_random_question_from_file(file_name):
    filesize = os.path.getsize(file_name)
    offset = random.randrange(filesize)

    f = open(file_name)
    f.seek(offset)  # go to random position
    f.readline()  # discard - bound to be partial line
    random_line = f.readline()  # bingo!

    # extra to handle last/first line edge cases
    if len(random_line) == 0:  # we have hit the end
        f.seek(0)
        random_line = f.readline()
    f.close()
    line = random_line.split("\t")
    question_id = line[INPUT_FILE_ID_INDEX]
    question = line[INPUT_FILE_QUESTION_INDEX]
    question = question.replace("\"", "")
    return question_id, question


def generate_multi_langs_samples():
    translator = Translator(PROJECT_ID)
    with open(LANG_TEST_FILE, "w") as output_file:
        writer = csv.writer(output_file)
        for i in range(NUM_OF_SAMPLES_FOR_LANG_TEST):
            print(i)
            question_id, question = get_random_question_from_file(INPUT_FILE)
            row = [question_id, question]
            for target_lang in TARGET_LANGS_TO_TEST:
                translation = translator.round_trip_translate(question, target_lang)
                row.append(translation)
            writer.writerow(row)


def generate_new_data_samples_with_rtt():
    translator = Translator(PROJECT_ID)
    input_file = open(INPUT_FILE)
    full_samples_file = open(FULL_NEW_SAMPLES_FILE, "w")
    full_samples_file_with_fallback = open(FULL_NEW_SAMPLES_FILE_WITH_FALLBACK, "w")

    # stats
    current_row_number = 0
    fallback_usage = 0
    fallback_fail = 0

    try:
        reader = csv.reader(input_file)
        full_samples_writer = csv.writer(full_samples_file)
        full_samples_with_fallback_writer = csv.writer(full_samples_file_with_fallback)

        for row in reader:
            # write the original row
            question = row[INPUT_FILE_QUESTION_INDEX]
            question = question.lower().strip()
            row[INPUT_FILE_QUESTION_INDEX] = question
            full_samples_writer.writerow(row)
            full_samples_with_fallback_writer.writerow(row)

            print("attempting row {}".format(current_row_number))
            question_id = row[INPUT_FILE_ID_INDEX]

            # generate new sample
            fallback_used = False
            translation = translator.round_trip_translate(question, TARGET_LANG)
            new_question_id = "{}_{}".format(question_id, TARGET_LANG)

            if translation == question:  # try fallback
                print("running fallback")
                fallback_usage += 1
                fallback_used = True
                new_question_id = "{}_{}".format(question_id, FALLBACK_TARGET_LANG)
                translation = translator.round_trip_translate(question, FALLBACK_TARGET_LANG)

                if translation == question:  # fallback failed
                    print("discarding row")
                    fallback_fail += 1
                    current_row_number += 1
                    continue

            # write new sample with full info to file
            new_sample_full = list(row)
            new_sample_full[INPUT_FILE_ID_INDEX] = new_question_id
            new_sample_full[INPUT_FILE_QUESTION_INDEX] = translation
            if not fallback_used:
                full_samples_writer.writerow(new_sample_full)
                full_samples_with_fallback_writer.writerow(new_sample_full)
            else:
                full_samples_with_fallback_writer.writerow(new_sample_full)
            current_row_number += 1

    finally:
        with open(STATS_FILE, "w") as stats:
            writer = csv.writer(stats)
            writer.writerow(["current row number", current_row_number])
            writer.writerow(["fallback usage", fallback_usage])
            writer.writerow(["fallback fail", fallback_fail])
        input_file.close()
        full_samples_file.close()
        full_samples_file_with_fallback.close()


def main():
    generate_new_data_samples_with_rtt()


if __name__ == "__main__":
    main()
