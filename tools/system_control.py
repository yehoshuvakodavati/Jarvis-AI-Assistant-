import subprocess
import webbrowser


def open_application(command):
    cmd = command.lower()

    if "notepad" in cmd:
        subprocess.Popen("notepad", shell=True)
        return "Commander, opening Notepad"

    elif "calculator" in cmd:
        subprocess.Popen("calc", shell=True)
        return "Commander, opening Calculator"

    elif "command prompt" in cmd or "cmd" in cmd:
        subprocess.Popen("start cmd", shell=True)
        return "Commander, opening Command Prompt"

    elif "terminal" in cmd:
        subprocess.Popen("start powershell", shell=True)
        return "Commander, opening Terminal"

    return None


def open_website(command):
    cmd = command.lower()

    if "youtube" in cmd:
        webbrowser.open("https://www.youtube.com")
        return "Commander, opening YouTube"

    elif "google" in cmd:
        webbrowser.open("https://www.google.com")
        return "Commander, opening Google"

    return None

def open_settings(command):
    cmd = command.lower()

    if "settings" in cmd:
        subprocess.Popen("start ms-settings:", shell=True)
        return "Commander, opening Settings"

    elif "display settings" in cmd:
        subprocess.Popen("start ms-settings:display", shell=True)
        return "Commander, opening Display Settings"

    elif "keyboard settings" in cmd:
        subprocess.Popen("start ms-settings:keyboard", shell=True)
        return "Commander, opening Keyboard Settings"

    elif "network settings" in cmd:
        subprocess.Popen("start ms-settings:network", shell=True)
        return "Commander, opening Network Settings"

    elif "bluetooth settings" in cmd:
        subprocess.Popen("start ms-settings:bluetooth", shell=True)
        return "Commander, opening Bluetooth Settings"

    elif "privacy settings" in cmd:
        subprocess.Popen("start ms-settings:privacy", shell=True)
        return "Commander, opening Privacy Settings"

    elif "home settings" in cmd:
        subprocess.Popen("start ms-settings:", shell=True)
        return "Commander, opening Settings Home"

    return None

def system_power(command):
    cmd = command.lower()

    if "shutdown" in cmd:
        return "CONFIRM_SHUTDOWN"

    elif "restart" in cmd:
        return "CONFIRM_RESTART"

    elif "sleep" in cmd:
        subprocess.Popen(
            "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            shell=True
        )
        return "Commander, putting system to sleep"

    elif "lock" in cmd:
        subprocess.Popen(
            "rundll32.exe user32.dll,LockWorkStation",
            shell=True
        )
        return "Commander, locking the system"

    return None

def shutdown_system():
    import subprocess
    subprocess.Popen("shutdown /s /t 1", shell=True)
    return "Commander, shutting down the system"


def restart_system():
    import subprocess
    subprocess.Popen("shutdown /r /t 1", shell=True)
    return "Commander, restarting the system"
def sleep_system():
    
    subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
    return "Commander, putting system to sleep"