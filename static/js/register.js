var myInput = document.getElementById("register_password");
var myConfirmInput = document.getElementById("register_confirm_password")
var letter = document.getElementById("letter");
var capital = document.getElementById("capital");
var number = document.getElementById("number");
var lengthReq = document.getElementById("length_req");
var submitButton = document.getElementById("registerUserButton");
var passwordsMustMatch = document.getElementById("passwords_must_match")

function passwordIsValidAndMatchesConfirmed(passwordInput, confirmPasswordInput, lengthReq, letterReq, capitalReq, numberReq) {
    return (lengthReq.classList.contains("password_valid") && 
    numberReq.classList.contains("password_valid") && 
    capitalReq.classList.contains("password_valid") && 
    letterReq.classList.contains("password_valid") &&
    passwordInput.value == confirmPasswordInput.value)

}


// When the user clicks on the password field, show the message box
myInput.onfocus = function() {
  document.getElementById("password_requirements_message").style.display = "block";
}

// When the user clicks outside of the password field, hide the message box
myInput.onblur = function() {
  document.getElementById("password_requirements_message").style.display = "none";
}

// When the user starts to type something inside the password field
myInput.onkeyup = function() {
  // Validate lowercase letters
  var lowerCaseLetters = /[a-z]/g;
  if(myInput.value.match(lowerCaseLetters)) {
    letter.classList.remove("password_invalid");
    letter.classList.add("password_valid");
  } else {
    letter.classList.remove("password_valid");
    letter.classList.add("password_invalid");
}

  // Validate capital letters
  var upperCaseLetters = /[A-Z]/g;
  if(myInput.value.match(upperCaseLetters)) {
    capital.classList.remove("password_invalid");
    capital.classList.add("password_valid");
  } else {
    capital.classList.remove("password_valid");
    capital.classList.add("password_invalid");
  }

  // Validate numbers
  var numbers = /[0-9]/g;
  if(myInput.value.match(numbers)) {
    number.classList.remove("password_invalid");
    number.classList.add("password_valid");
  } else {
    number.classList.remove("password_valid");
    number.classList.add("password_invalid");
  }

  // Validate length
  if(myInput.value.length >= 8) {
    lengthReq.classList.remove("password_invalid");
    lengthReq.classList.add("password_valid");
  } else {
    lengthReq.classList.remove("password_valid");
    lengthReq.classList.add("password_invalid");
  }
  submitButton.disabled = !passwordIsValidAndMatchesConfirmed(myInput, myConfirmInput, lengthReq, letter, capital, number)
}

myConfirmInput.onkeyup = function() {
    if (myConfirmInput.value != myInput.value) {
        passwordsMustMatch.style.display = "block"
    } else{
        passwordsMustMatch.style.display = "none"
    }
    submitButton.disabled = !passwordIsValidAndMatchesConfirmed(myInput, myConfirmInput, lengthReq, letter, capital, number)
}