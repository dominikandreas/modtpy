const handleError = error => {
  $("#printer-status").text(error.message);
};

const getStatus = () => {
  $.getJSON({
    url: "/printer/status"
  })
    .done(payload => {
      setStatus(payload);
    })
    .fail(payload => {
      handleError(payload.responseJSON);
    });
};

const setStatus = status => {
  $("#printer-status").text(status.status.state);
};

const pollStatus = () => {
  getStatus();
  setInterval(() => {
    getStatus();
  }, 3000);
};

$(() => {
  pollStatus();
});
