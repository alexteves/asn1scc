#!/usr/bin/env python

import os
import sys
import itertools
import shutil
import getopt
import subprocess

# Globals

rootDir = None
language = None
targetDir = None
nTests = None


def CreateACNFile(content):
    str_start = "TEST-CASE DEFINITIONS ::= BEGIN\n"
    str_end = "END\n"
    f = open(targetDir+os.sep+"sample1.acn", 'w')
    f.write("-- Auto generated file\n\n")
    f.write(str_start)
    f.write("\t"+content+"\n")
    f.write(str_end)
    f.close()


def mysystem(cmd, bCanFail):
    f = open("log.txt", 'a')
    f.write(cmd+"\n")
    f.close()
    ret = subprocess.call(cmd, shell=True)
    if ret != 0 and not bCanFail:
        PrintFailed(cmd)
        mysystem("cat tmp.err", True)
        sys.exit(1)
    return ret


def resolvedir(path):
    if sys.platform == 'cygwin':
        return "c:\\"+"\\".join(path.split("/")[3:])
    else:
        return path


def PrintFailed(mssg):
    print "\033[31m%-65s\033[0m" % (mssg)


def PrintSucceededAsExpected(mssg):
    print "\033[32m%-65s\033[0m" % (mssg)


def PrintWarning(mssg):
    print "\033[93m%-65s\033[0m" % (mssg)


#behavior 0 :test case must pass
#behavior 1 :test case must fail in the asn1f.exe, with specific error message
#behavior 2 :test case must fail during execution of the generated executable
def RunTestCase(asn1, acn, behavior, expErrMsg):
    global nTests

    print asn1, acn

    asn1File = targetDir+os.sep+"sample1.asn1"
    acnFile = targetDir+os.sep+"sample1.acn"
    res = mysystem(
        "Asn1f2.exe  -" + language + "  -ACN -typePrefix gmamais_ " +
        "-atc -o '" + resolvedir(targetDir) + "' '" + resolvedir(asn1File) +
        "' '" + resolvedir(acnFile)+"' >tmp.err 2>&1", True)
    ferr = open("tmp.err", 'r')
    err_msg = ferr.read().replace("\r\n", "").replace("\n", "")
    ferr.close()
    if behavior == 0 or behavior == 2:
        if res != 0 or err_msg != "":
            PrintFailed("Asn.1 compiler failed")
            print "Asn.1 compiler error is: "+err_msg
            sys.exit(1)
    else:
        if res == 0 or err_msg != expErrMsg:
            PrintFailed(
                "Asn.1 compiler didn't fail or failed with "
                "different error message")
            print "Expected/current messages: "
            print "'"+expErrMsg+"'"
            print "'"+err_msg+"'"
            sys.exit(1)
        else:
            nTests += 1
            return

    if language == "c":
        res = mysystem("cd "+targetDir+os.sep+"; CC=gcc make coverage", False)
        f = open(targetDir+os.sep+"sample1.c.gcov", 'r')
        lines = [
            l
            for l in f.readlines()
            if ("####" in l) and ("//COVERAGE_IGNORE" not in l)]
        if len(lines) > 0:
            PrintFailed("coverage failed. (less than 100%)")
            sys.exit(1)
    else:
        os.chdir(targetDir)
        mysystem("./runSpark.sh >../tmp.err  2>&1", False)
        f = open("examiner/pogs.sum", 'r')
        totalsline = [
            l
            for l in f.readlines()
            if l.startswith("Totals:")][0]
        if "<<<" in totalsline:
            PrintFailed("Victor failed")
            sys.exit(1)

        res = mysystem("CC=gcc make coverage >covlog.txt 2>&1", True)
        if res != 0 and behavior != 2:
            PrintFailed("run time failure")
            PrintFailed("see covlog.txt")
            sys.exit(1)
        elif behavior == 2 and res == 2:
            PrintSucceededAsExpected(
                "Test cases failed at run-time as expected")
        elif behavior == 2 and res == 0:
            PrintFailed(
                "ERROR: Executable didn't fail as it was expected to do...")
            sys.exit(1)
        elif behavior == 0 and res == 0:
            #-- NOCOVERAGE
            doCoverage = "-- NOCOVERAGE" not in \
                open("sample1.asn1", 'r').readlines()[0]
            if doCoverage:
                lmbd = lambda l: "test_case.adb" not in l
                lines = list(
                    itertools.dropwhile(
                        lmbd, open("covlog.txt", 'r').readlines()))
                lines = list(itertools.dropwhile(lmbd, lines[1:]))
                excLine = [
                    l
                    for l in list(lines)
                    if "executed" in l][0]
                if "executed:100.00" not in excLine:
                    PrintFailed("coverage error (less than 100%)")
                    sys.exit(1)
        else:
            print res, behavior
            PrintWarning(
                "BUG in python script, Unexpected combination "
                "of res, behavior")
        os.chdir("..")
    nTests += 1


def DoWork_ACN(asn1file):
    print language, "ACN", asn1file

    fnameASN = asn1file.strip()
    if not os.path.exists(fnameASN):
        print "File '"+fnameASN+"' does not exist! "
        sys.exit(1)

    f = open(fnameASN, 'r')
    lines = f.readlines()
    for line in lines:
        if line.find("--TCLS") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCLS")[1].strip()
            CreateACNFile(tmp_line)
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 0, "")
        elif line.find("--TCLFC") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCLFC")[1].strip()
            tmp_err = tmp_line.split("$$$")[1].strip()
            tmp_line = tmp_line.split("$$$")[0].strip()
            CreateACNFile(tmp_line)
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 1, tmp_err)
        elif line.find("--TCLFE") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCLFE")[1].strip()
            tmp_err = tmp_line.split("$$$")[1].strip()
            tmp_line = tmp_line.split("$$$")[0].strip()
            CreateACNFile(tmp_line)
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 2, tmp_err)
        # # for file (TCF)
        elif line.find("--TCFS") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCFS")[1].strip()
            shutil.copyfile(
                testCaseDir+os.sep+tmp_line, targetDir+os.sep+"sample1.acn")
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 0, "")
        elif line.find("--TCFFC") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCFFC")[1].strip()
            tmp_err = tmp_line.split("$$$")[1].strip()
            tmp_line = tmp_line.split("$$$")[0].strip()
            shutil.copyfile(
                testCaseDir+os.sep+tmp_line, targetDir+os.sep+"sample1.acn")
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 1, tmp_err)
        elif line.find("--TCFFE") == 0:
            shutil.rmtree(targetDir, ignore_errors=True)
            os.mkdir(targetDir)
            testCaseDir = os.path.dirname(os.path.abspath(fnameASN))
            shutil.copyfile(fnameASN, targetDir+os.sep+"sample1.asn1")
            tmp_line = line.split("--TCFFE")[1].strip()
            tmp_err = tmp_line.split("$$$")[1].strip()
            tmp_line = tmp_line.split("$$$")[0].strip()
            shutil.copyfile(
                testCaseDir+os.sep+tmp_line, targetDir+os.sep+"sample1.acn")
            RunTestCase(
                os.sep.join(asn1file.split(os.sep)[-2:]), tmp_line, 2, tmp_err)
        elif line.find("--TCBREAK") == 0:
            sys.exit(0)
        else:
            continue


def GetBehavior(asn1File):
    if asn1File.find("FAIL") != -1:
        f = open(asn1File, 'r')
        line = f.readlines()[0]
        if line.find("$$$") != -1:
            errCode = int(line.split("$$$")[1])
            errMsg = line.split("$$$")[2].strip()
            errMsg = errMsg.replace("\r\n", "").replace("\n", "")
            return (errCode, errMsg)
    return (0, "")


knownIssues = {
    ("Ada", "uPER", "12-set/007.asn1"): "",
    ("c", "uPER", "12-set/007.asn1"): "",
    ("c", "uPER", "13-set-of/003_FAIL.asn1"): "",
    ("Ada", "uPER", "15-WITH-COMPONENT/003.asn1"): "",
    ("Ada", "BER", "15-WITH-COMPONENT/003.asn1"): "",
    ("Ada", "XER", "15-WITH-COMPONENT/003.asn1"): "",
    ("Ada", "XER", "11-BitString/003.asn1"): "",
    ("c", "uPER", "05-struct/006.asn1"): "",
    ("c", "XER", "11-BitString/002.asn1"): "",
    ("c", "XER", "11-BitString/003.asn1"): "",
    ("c", "BER", "11-BitString/002.asn1"):
    "RTL doesn't currently support the decoding of "
    "constructed bit strings. To be fixed!",
    ("c", "BER", "11-BitString/003.asn1"):
    "RTL doesn't currently support the decoding of "
    "constructed bit strings. To be fixed!",
    ("Ada", "BER", "11-BitString/002.asn1"):
    "RTL doesn't currently support the decoding of "
    "constructed bit strings. To be fixed!",
    ("Ada", "BER", "11-BitString/003.asn1"):
    "RTL doesn't currently support the decoding of "
    "constructed bit strings. To be fixed!",
    ("c", "uPER", "12-set/006.asn1"): ""
}


def submain(lang, encoding, testCaseSet):
    global language, targetDir

    language = lang
    targetDir = rootDir + os.sep + "tmp"

    if os.path.exists("tmp"):
        shutil.rmtree("tmp")
    os.mkdir("tmp")

    if testCaseSet == "":
        testCaseSet = rootDir + os.sep + "test-cases" + os.sep + "acn"

    funcName = "DoWork_"+encoding
    if os.path.isfile(testCaseSet):
        globals()[funcName](os.path.abspath(testCaseSet))
    else:
        for curDir, _, files in os.walk(testCaseSet):
            if -1 != curDir.find('.svn'):
                continue
            asn1files = [x for x in files if x.endswith(".asn1")]
            for asn1file in asn1files:
                globals()[funcName](
                    os.path.abspath(curDir + os.sep + asn1file))


def usage():
    print "Usage: ", sys.argv[0], " <options>"
    print "where <options> are:"
    print "Mandatory:"
    print "     -l, --lang  <language_name>"
    print "           where <language_name> is c or Ada"
    print "Optional:"
    print "     -t, --testCaseSet  <asn1File> or <testcaseDir>"
    sys.exit(1)


def main():
    global rootDir, nTests

    rootDir = os.path.abspath(
        os.path.dirname(os.path.abspath(sys.argv[0]))+os.sep+"..")
    nTests = 0

    if len(sys.argv) == 1:
        usage()

    try:
        args = sys.argv[1:]
        optlist, args = getopt.gnu_getopt(
            args, "al:t:", ['all', 'lang=', 'testCaseSet='])
    except:
        usage()
    if args != []:
        print "Invalid arguments: ", args
        usage()

    lang = ""
    testCaseSet = ""
    bAll = False
    for opt, arg in optlist:
        if opt in ("-a", "--all"):
            bAll = True
        elif opt in ("-l", "--lang"):
            lang = arg
        elif opt in ("-t", "--testCase"):
            testCaseSet = arg
    if bAll:
        f = open("log.txt", 'a')
        f.write("==========================================\n")
        f.close()
        submain("c", "ACN", "")
        submain("Ada", "ACN", "")
    else:
        if lang not in ["c", "Ada"]:
            print "Invalid language argument"
            usage()

        if testCaseSet != "" and not os.path.exists(testCaseSet):
            print "File '" + testCaseSet + "' not found."
            usage()
        if lang.lower() == "c":
            os.putenv("PATH", "/usr/bin:" + os.getenv("PATH"))

        f = open("log.txt", 'a')
        f.write("==========================================\n")
        f.close()
        submain(lang, "ACN", testCaseSet)
    print "Test run ended succesfully. Number of test cases run :", nTests


if __name__ == "__main__":
    main()
