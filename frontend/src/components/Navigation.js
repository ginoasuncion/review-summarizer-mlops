import React from 'react';
import { Paper, Tabs, Tab, Box } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { Schedule, Search } from '@mui/icons-material';

function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();

  const getCurrentTab = () => {
    switch (location.pathname) {
      case '/':
        return 0;
      case '/manual':
        return 1;
      default:
        return 0;
    }
  };

  const handleTabChange = (event, newValue) => {
    switch (newValue) {
      case 0:
        navigate('/');
        break;
      case 1:
        navigate('/manual');
        break;
      default:
        navigate('/');
    }
  };

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
      <Paper elevation={1}>
        <Tabs
          value={getCurrentTab()}
          onChange={handleTabChange}
          aria-label="navigation tabs"
          centered
        >
          <Tab 
            icon={<Schedule />} 
            label="Schedule" 
            iconPosition="start"
          />
        </Tabs>
      </Paper>
    </Box>
  );
}

export default Navigation; 