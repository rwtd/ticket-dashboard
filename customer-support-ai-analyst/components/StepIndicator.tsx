
import React from 'react';
import { AppStep } from '../types';

interface StepIndicatorProps {
  currentStep: AppStep;
}

const steps = [
  { id: AppStep.SelectDataSource, name: 'Connect Data' },
  { id: AppStep.UploadData, name: 'Upload Files' },
  { id: AppStep.ConfirmSchema, name: 'Confirm Schema' },
  { id: AppStep.Chat, name: 'Analyze & Chat' },
];

// This mapping ensures we can find the numeric index of a step
const stepOrder: AppStep[] = [AppStep.SelectDataSource, AppStep.UploadData, AppStep.ConfirmSchema, AppStep.Chat];


const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => {
  const currentStepIndex = stepOrder.indexOf(currentStep);

  return (
    <nav aria-label="Progress">
      <ol role="list" className="flex items-center">
        {steps.map((step, stepIdx) => {
            // Remap UploadData to SelectDataSource for visual grouping
            const effectiveCurrentStep = currentStep === AppStep.UploadData ? AppStep.SelectDataSource : currentStep;
            const effectiveCurrentStepIndex = stepOrder.indexOf(effectiveCurrentStep);

            return(
          <li key={step.name} className={`relative ${stepIdx !== steps.length - 1 ? 'pr-8 sm:pr-20' : ''}`}>
            {effectiveCurrentStepIndex > stepIdx ? (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-indigo-600" />
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center bg-indigo-600 rounded-full">
                  <svg className="h-5 w-5 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.052-.143z" clipRule="evenodd" />
                  </svg>
                  <span className="sr-only">{step.name} - Completed</span>
                </div>
              </>
            ) : effectiveCurrentStepIndex === stepIdx ? (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200 dark:bg-gray-700" />
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center bg-white dark:bg-gray-800 border-2 border-indigo-600 rounded-full">
                  <span className="h-2.5 w-2.5 bg-indigo-600 rounded-full" aria-hidden="true" />
                  <span className="sr-only">{step.name} - Current</span>
                </div>
              </>
            ) : (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200 dark:bg-gray-700" />
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center bg-white dark:bg-gray-800 border-2 border-gray-300 dark:border-gray-600 rounded-full">
                   <span className="sr-only">{step.name} - Upcoming</span>
                </div>
              </>
            )}
             <p className="absolute -bottom-6 w-max -left-2 text-xs font-medium text-gray-700 dark:text-gray-300">{step.name}</p>
          </li>
        )})}
      </ol>
    </nav>
  );
};


export default StepIndicator;
