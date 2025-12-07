// Get current weekday in Poland
function getPolandWeekday() {
  const date = new Date();
  const options = { timeZone: 'Europe/Warsaw', weekday: 'long' };
  const dayName = new Intl.DateTimeFormat('en-US', options).format(date);
  return dayName;
}

// Get default service ID based on Poland weekday
export function getDefaultService() {
  const day = getPolandWeekday();
  switch (day) {
    case 'Monday':
    case 'Tuesday':
    case 'Wednesday':
      return 'service_1';
    case 'Thursday':
      return 'service_5';
    case 'Friday':
      return 'service_4';
    case 'Saturday':
      return 'service_2';
    case 'Sunday':
      return 'service_3';
    default:
      return 'service_1';
  }
}
