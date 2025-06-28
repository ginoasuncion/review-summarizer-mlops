import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stepper,
  Step,
  StepLabel,
  Paper,
  Divider
} from '@mui/material';
import { Search, Refresh, QueryStats } from '@mui/icons-material';
import { searchYouTube, triggerProductSummary, queryProduct } from '../services/api';

function ManualPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [maxResults, setMaxResults] = useState(5);
  const [productName, setProductName] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState({});
  const [error, setError] = useState(null);

  const steps = [
    'Search YouTube',
    'Wait for Processing',
    'Generate Product Summary',
    'Query Results'
  ];

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await searchYouTube(searchQuery, maxResults);
      setResults(prev => ({ ...prev, search: result }));
      setActiveStep(1);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateSummary = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await triggerProductSummary();
      setResults(prev => ({ ...prev, summary: result }));
      setActiveStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuery = async () => {
    if (!productName.trim()) {
      setError('Please enter a product name');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await queryProduct(productName);
      setResults(prev => ({ ...prev, query: result }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resetProcess = () => {
    setActiveStep(0);
    setResults({});
    setError(null);
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Manual Process
      </Typography>

      {/* Stepper */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Stepper activeStep={activeStep} alternativeLabel>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Step 1: Search YouTube */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Step 1: Search YouTube
              </Typography>
              <Box component="form" sx={{ mt: 2 }}>
                <TextField
                  fullWidth
                  label="Search Query"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g., Nike Air Jordan 1 review"
                  sx={{ mb: 2 }}
                />
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Max Results</InputLabel>
                  <Select
                    value={maxResults}
                    label="Max Results"
                    onChange={(e) => setMaxResults(e.target.value)}
                  >
                    <MenuItem value={3}>3 videos</MenuItem>
                    <MenuItem value={5}>5 videos</MenuItem>
                    <MenuItem value={10}>10 videos</MenuItem>
                    <MenuItem value={15}>15 videos</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  startIcon={loading ? <CircularProgress size={20} /> : <Search />}
                  onClick={handleSearch}
                  disabled={loading || activeStep > 0}
                  fullWidth
                >
                  {loading ? 'Searching...' : 'Search YouTube'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Step 2: Wait for Processing */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Step 2: Wait for Processing
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                After searching, the system will automatically process videos through:
              </Typography>
              <Typography variant="body2" component="div">
                • Transcript extraction
              </Typography>
              <Typography variant="body2" component="div">
                • LLM summarization
              </Typography>
              <Typography variant="body2" component="div">
                • Quality evaluation
              </Typography>
              <Typography variant="body2" sx={{ mt: 2 }}>
                <strong>Wait 10-15 minutes</strong> for processing to complete, then proceed to Step 3.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Step 3: Generate Product Summary */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Step 3: Generate Product Summary
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Trigger the product summary generation process to aggregate all processed videos.
              </Typography>
              <Button
                variant="contained"
                startIcon={loading ? <CircularProgress size={20} /> : <Refresh />}
                onClick={handleGenerateSummary}
                disabled={loading || activeStep < 1}
                fullWidth
              >
                {loading ? 'Generating...' : 'Generate Product Summary'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Step 4: Query Results */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Step 4: Query Results
              </Typography>
              <TextField
                fullWidth
                label="Product Name"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="e.g., Nike Air Jordan 1"
                sx={{ mb: 2 }}
              />
              <Button
                variant="contained"
                startIcon={loading ? <CircularProgress size={20} /> : <QueryStats />}
                onClick={handleQuery}
                disabled={loading || activeStep < 3}
                fullWidth
              >
                {loading ? 'Querying...' : 'Query Product Summary'}
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Results Display */}
      {Object.keys(results).length > 0 && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Results
            </Typography>
            
            {results.search && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Search Results:
                </Typography>
                <Alert severity="info">
                  Status: {results.search.status}
                </Alert>
              </Box>
            )}

            {results.summary && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Summary Generation:
                </Typography>
                <Alert severity="info">
                  {JSON.stringify(results.summary, null, 2)}
                </Alert>
              </Box>
            )}

            {results.query && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Query Results:
                </Typography>
                <Alert severity="info">
                  {JSON.stringify(results.query, null, 2)}
                </Alert>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />
            
            <Button
              variant="outlined"
              onClick={resetProcess}
              fullWidth
            >
              Start New Process
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Instructions */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Manual Process Instructions
          </Typography>
          <Typography variant="body2" paragraph>
            <strong>Step 1:</strong> Search YouTube for review videos of a specific shoe
          </Typography>
          <Typography variant="body2" paragraph>
            <strong>Step 2:</strong> Wait for the system to process videos (transcript extraction, summarization, evaluation)
          </Typography>
          <Typography variant="body2" paragraph>
            <strong>Step 3:</strong> Generate a unified product summary from all processed videos
          </Typography>
          <Typography variant="body2" paragraph>
            <strong>Step 4:</strong> Query the generated product summary to view results
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This manual process gives you control over each step, while the automated scheduler handles everything in one go.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}

export default ManualPage; 