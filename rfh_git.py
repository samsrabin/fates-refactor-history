"""
Class useful for git stuff
"""
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=too-many-arguments
# pylint: disable=fixme

import os
import shutil
import subprocess
import re

import options as other_options


def run_git_cmd(git_cmd, cwd=os.getcwd()):
    try:
        git_result = subprocess.check_output(
            git_cmd.split(" "),
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=cwd,
        ).splitlines()
    except subprocess.CalledProcessError as e:
        print("Command: " + " ".join(e.cmd))
        print("Working directory: " + cwd)
        print("Message: ", e.stdout)
        raise e
    except:  # pylint: disable=try-except-raise
        raise
    return git_result


class Rfh_Git:
    def __init__(self, publish_dir, logfile):
        self.publish_dir = publish_dir
        self.check_pub_dir_clean()

        self.logfile = logfile
        self.publish_url = self.get_publish_url()

    def check_pub_dir_clean(self):
        status = run_git_cmd(f"git -C {self.publish_dir} status")
        if status[-1] != "nothing to commit, working tree clean":
            raise RuntimeError(f"self.publish_dir not clean: {self.publish_dir}")

    def commit(self, modified_files, new_files):
        status = run_git_cmd(f"git -C {self.publish_dir} status")
        if status[-1] != "nothing to commit, working tree clean":
            # Stage
            print("Staging...")
            git_cmd = (
                f"git -C {self.publish_dir} add {os.path.join(self.publish_dir, '*')}"
            )
            status = run_git_cmd(git_cmd)

            # Commit
            print("Committing...")
            git_cmd = f"git -C {self.publish_dir} commit -m Update"
            status = run_git_cmd(git_cmd)

            # Push
            print("Pushing...")
            git_cmd = f"git -C {self.publish_dir} push"
            status = run_git_cmd(git_cmd)

            print("Done! Published to:")
            for f in modified_files + new_files:
                file_url = self.publish_url + os.path.basename(f)
                print("   " + file_url)
        else:
            print("Nothing to commit")

    def get_publish_url(self):
        try:
            PUBLISH_URL = other_options.PUBLISH_URL
        except AttributeError:
            cmd = "git config --get remote.origin.url"
            publish_repo_url = run_git_cmd(cmd, cwd=self.publish_dir)[0]

            cmd = "git rev-parse --show-toplevel"
            publish_dir_repo_top = run_git_cmd(cmd, cwd=self.publish_dir)[0]
            subdirs = str(os.path.realpath(self.publish_dir)).replace(
                publish_dir_repo_top, ""
            )

            if "git@github.com:" in publish_repo_url:
                gh_user = re.compile(r"git@github.com:(\w+)").findall(publish_repo_url)[
                    0
                ]
                repo_name = re.compile(r"/(.+).git").findall(publish_repo_url)[0]
                PUBLISH_URL = (
                    f"https://{gh_user}.github.io/{repo_name}" + subdirs + "/"
                )
            else:
                raise NotImplementedError(  # pylint: disable=raise-missing-from
                    " ".join(
                        [
                            f"Not sure how to handle publish_repo_url {publish_repo_url}.",
                            "Provide PUBLISH_URL in options.py.",
                        ]
                    )
                )
        except:  # pylint: disable=try-except-raise
            raise
        return PUBLISH_URL

    def publish(self):
        # Ensure publishing dir is clean
        self.check_pub_dir_clean()

        # Rename log file
        destfile = os.path.join(
            self.publish_dir, os.path.basename(self.logfile).replace("html.tmp", "html")
        )
        shutil.move(self.logfile, destfile)

        status = run_git_cmd(f"git -C {self.publish_dir} status")
        modified_files = []
        new_files = []
        in_untracked_files = False
        for l in status:
            if not in_untracked_files:
                if re.compile("^\tmodified:").match(l):
                    modified_files.append(l.split(" ")[-1])
                elif l == "Untracked files:":
                    in_untracked_files = True
            else:
                if l == "":
                    break
                if (
                    l
                    != '  (use "git add <file>..." to include in what will be committed)'
                ):
                    new_files.append(l.replace("\t", ""))
        if modified_files:
            print("Updating files:\n   " + "\n   ".join(modified_files))
        if new_files:
            print("Adding files:\n   " + "\n   ".join(new_files))

        self.commit(modified_files, new_files)
