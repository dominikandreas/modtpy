const handleError = error => {
  if (error !== undefined && error.message !== undefined) {
    $("#printer-status").text(error.message);
  }
};

const stateTypes = {
  STATE_LOADFIL_HEATING: "Loading filament: heating",
  STATE_LOADFIL_EXTRUDING: "Loading filament: extruding",
  STATE_REMFIL_HEATING: "Unloading filament: heating",
  STATE_REMFIL_RETRACTING: "Unloading filament: retracting",
  STATE_IDLE: "Idle",
  STATE_FILE_RX: "Receiving GCODE",
  STATE_JOB_QUEUED: "Job queued",
  STATE_JOB_PREP: "Preparing Job",
  STATE_HOMING_XY: "Calibrating X/Y axis",
  STATE_HOMING_HEATING: "Heating up",
  STATE_HOMING_Z_ROUGH: "Calibrating Z axis rough",
  STATE_HOMING_Z_FINE: "Calibrating Z axis fine",
  STATE_BUILDING: "Printing",
  STATE_EXEC_PAUSE_CMD: "Pausing",
  STATE_PAUSED: "Paused",
  STATE_UNPAUSED: "Resuming",
  STATE_MECH_READY: "Print finished"
};

const getStatus = () => {
  $.getJSON({
    url: "/printer/status"
  })
    .done(payload => {
      setMode(payload.mode);
      setStatus(payload.status);
      setLogs(payload.logs);
    })
    .fail(payload => {
      handleError(payload.responseJSON);
    });
};


document.logged_messages = {};


const setLogs = logs => {
  let logs_div = $(".logs")[0];
  let last_el = undefined;
  logs.forEach(log => {
    if (document.logged_messages[log.id] === undefined){
      let el = document.createElement("p");
      document.logged_messages[log.id] = 1
      el.innerHTML = document.ansispan(log.message);
      logs_div.appendChild(el);
      last_el = el;
    }
  })
  if (last_el !== undefined){
    last_el.scrollIntoView()
  }
}

const setStatus = status => {
  if (!status || !status.status) {
    $(".modtpy-status").text("");
    $(".modtpy-status-temp").text("");
    $(".modtpy-status-temp-0").show();
    $(".modtpy-status-temp-1").hide();
    $(".modtpy-status-temp-2").hide();
    $(".modtpy-status-temp-3").hide();
    $(".modtpy-status-temp-4").hide();
    return;
  }
  let statusMsg = stateTypes[status.status.state];
  let printOptions = $("#print-options")[0];
  let printerBtn = $("#btn-printer-button")[0];
  printerBtn.style.display = "none";
  if (statusMsg === "Job queued"){
    printOptions.style.display = "inline";
  } else if (statusMsg === "Printing"){
    printerBtn.style.display = "inline";
    printerBtn.innerText = "Pause Print";
  } else if (statusMsg === "Paused"){
    printerBtn.style.display = "inline";
    printerBtn.innerText = "Resume Print";
  }

  $(".modtpy-status").text(statusMsg);
  setTemperature(
    status.status.extruder_temperature,
    status.status.extruder_target_temperature
  );

  if (status.job !== undefined) {
    setProgress(status.job.progress);
  }
};

const setTemperature = (current, max) => {
  $(".modtpy-status-temp").text(current + "° / " + max + "°");
  $(".modtpy-status-temp-0").hide();
  $(".modtpy-status-temp-1").hide();
  $(".modtpy-status-temp-2").hide();
  $(".modtpy-status-temp-3").hide();
  $(".modtpy-status-temp-4").hide();
  const ratio = Math.max(Math.min(current / max, 1), 0);
  const scale = Math.round(ratio * 4);
  $(".modtpy-status-temp-" + scale).show();
};

const setProgress = progress => {
  try{
     parseInt(progress);
     let el = $(".modtpy-status-progress-display");
     el.text(progress + "%");
     el.show()
     $(".modtpy-status-progress").show();
  } catch (e) {
    $(".modtpy-status-progress").hide();
    $(".modtpy-status-progress-display").hide()
  }
}

const setMode = mode => {
  mode = mode.toUpperCase();
  if (mode === "DISCONNECTED" || mode === "DFU") {
    $(".modtpy-mode-connected").hide();
    $(".modtpy-mode-disconnected").show();
  } else if (mode === "OPERATE") {
    $(".modtpy-mode-connected").show();
    $(".modtpy-mode-disconnected").hide();
  }
  $(".modtpy-mode").text(mode.toLowerCase());
};

const pollStatus = () => {
  getStatus();
  setInterval(getStatus, 2000);
};


const loadFilament = () => {
  $.getJSON({
    url: "/printer/load-filament"
  }).done(payload => {
    setMode(payload.mode);
    setStatus(payload.status);
  }).fail(payload => {
    handleError(payload.responseJSON);
  });
}

const unloadFilament = () => {
  $.getJSON({
    url: "/printer/unload-filament"
  }).done(payload => {
    setMode(payload.mode);
    setStatus(payload.status);
  }).fail(payload => {
    handleError(payload.responseJSON);
  });
}

const uploadFile = (file, shouldOptimize, onSuccess) => {
  let fd = new FormData();
  fd.append('file', file);
  fd.append('optimize', !!shouldOptimize)
  $(".modtpy-status").text("Uploading file...");
  $.ajax({
      url: 'printer/upload-gcode',
      type: 'post',
      data: fd,
      contentType: false,
      processData: false,

      success: function(response){
        $(".modtpy-status").text("Upload complete");
        if (onSuccess !== undefined){
          onSuccess(response);
        }
      },

      error: function(request, status, error){
        const msg = ("Error during file upload: " + (status ? status: "") + " " + (error ? error: ""))
        $(".modtpy-status").text(msg);
        console.log(msg);
      },

      complete: function(){
        $("#upload-form")[0].reset();
      }

  });
}

const chooseFile = () => {
  let chooseBtn = $("#gcode_btn_file_choose")[0];
  let uploadBtn = $("#btn-start-print")[0];
  let optionsDiv = $("#print-options")[0];
  let fileDescr = $("#file-description")[0];

  chooseBtn.onchange = (event) =>{

    if (chooseBtn.files.length ===0 ) {
      fileDescr.innerText = "";
      return
    }
    optionsDiv.style.display = "block";

    let file = chooseBtn.files[0];
    fileDescr.innerText = file.name;

    uploadBtn.onclick = () => {
      let shouldOptimize = $("#checkbox-optimize-gcode")[0].checked;
      uploadFile(file, shouldOptimize, () => {optionsDiv.style.display = "none";});
    }

  }

  chooseBtn.click();
}

const pressButton = () => {
  $.getJSON({
    url: "/printer/press-button"
  });
}

$(() => {
  pollStatus();
  $("#btn-load")[0].onclick = loadFilament;
  $("#btn-unload")[0].onclick = unloadFilament;
  $("#btn-gcode")[0].onclick = chooseFile;
  $("#btn-printer-button")[0].onclick = pressButton;
});
