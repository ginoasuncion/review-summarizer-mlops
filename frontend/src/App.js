import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, AppBar, Toolbar, Typography, Container } from '@mui/material';
import Navigation from './components/Navigation';
import SchedulePage from './pages/SchedulePage';
import ManualPage from './pages/ManualPage';

function App() {
  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            🏃‍♂️ Shoe Review Summarizer
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Navigation />
      
      <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
        <Routes>
          <Route path="/" element={<SchedulePage />} />
          <Route path="/manual" element={<ManualPage />} />
        </Routes>
      </Container>
    </Box>
  );
}

export default App; 