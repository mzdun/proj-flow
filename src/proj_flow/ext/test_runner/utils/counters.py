# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from dataclasses import dataclass, field


class color:
    reset = "\033[m"
    counter = "\033[2;49;92m"
    name = "\033[0;49;90m"
    failed = "\033[0;49;91m"
    passed = "\033[2;49;92m"
    skipped = "\033[0;49;34m"


class TaskResult:
    OK = 0
    SKIPPED = 1
    SAVED = 2
    FAILED = 3
    CLIP_FAILED = 4


@dataclass
class Counters:
    error_counter: int = 0
    skip_counter: int = 0
    save_counter: int = 0
    echo: list[str] = field(default_factory=list)

    def report(self, outcome: int, test_id: str, message: str | None):
        if outcome == TaskResult.SKIPPED:
            print(f"{test_id} {color.skipped}SKIPPED{color.reset}")
            self.skip_counter += 1
            return

        if outcome == TaskResult.SAVED:
            print(f"{test_id} {color.skipped}saved{color.reset}")
            self.skip_counter += 1
            self.save_counter += 1
            return

        if outcome == TaskResult.CLIP_FAILED:
            msg = f"{test_id} {color.failed}FAILED (unknown check '{message}'){color.reset}"
            print(msg)
            self.echo.append(msg)
            self.error_counter += 1
            return

        if outcome == TaskResult.OK:
            print(f"{test_id} {color.passed}PASSED{color.reset}")
            return

        if message is not None:
            print(message)
        msg = f"{test_id} {color.failed}FAILED{color.reset}"
        print(msg)
        self.echo.append(msg)
        self.error_counter += 1

    def summary(self, counter: int):
        print(f"Failed {self.error_counter}/{counter}")
        if self.skip_counter > 0:
            skip_test = "test" if self.skip_counter == 1 else "tests"
            if self.save_counter > 0:
                print(
                    f"Skipped {self.skip_counter} {skip_test} (including {self.save_counter} due to saving)"
                )
            else:
                print(f"Skipped {self.skip_counter} {skip_test}")

        if len(self.echo):
            print()
        for echo in self.echo:
            print(echo)

        return self.error_counter == 0
